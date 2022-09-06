import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable

from aiofiles import open as aio_open
from git_interface.archive import get_archive_buffered
from git_interface.branch import count_branches, get_branches
from git_interface.datatypes import ArchiveTypes
from git_interface.exceptions import GitException
from git_interface.helpers import subprocess_run
from git_interface.tag import list_tags

from .discovery import find_repos

logger = logging.getLogger("archiver")


@dataclass
class ArchiverOptions:
    archive_type: ArchiveTypes
    dry_run: bool = False
    archive_branches: bool = False
    archive_tags: bool = False
    create_bundle: bool = False
    skip_list: list = field(default_factory=list),
    workers: int = 3,


@dataclass
class WorkerTask:
    func: Awaitable
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)


# TODO use git-interface implementation, when available
async def create_bundle(git_repo: Path, dst_path: Path):
    args = ["git", "-C", str(git_repo), "bundle",
            "create", str(dst_path), "--all"]
    process_status = await subprocess_run(args)
    if process_status.returncode != 0:
        stderr = process_status.stderr.decode()
        raise GitException(stderr)


def make_archive_name(name: str, archive_type: ArchiveTypes) -> str:
    return f"{name}.{archive_type.value}"


async def archive_repo(src_path: Path, dst_path: Path, tree_ish: str, options: ArchiverOptions):
    logger.info(
        "started archiving '%s' to '%s' at '%s'",
        src_path, dst_path, tree_ish
    )
    if options.dry_run:
        _ = [_ async for _ in get_archive_buffered(src_path, options.archive_type, tree_ish)]
    else:
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        async with aio_open(dst_path, "wb") as fo:
            async for chunk in get_archive_buffered(src_path, options.archive_type, tree_ish):
                await fo.write(chunk)

    logger.info(
        "done archiving '%s' to '%s' at '%s'",
        src_path, dst_path, tree_ish
    )


async def archive_bundle(src_path: Path, dst_path: Path, options: ArchiverOptions):
    logger.info("creating bundle of '%s' to '%s'", src_path, dst_path)
    if not options.dry_run:
        await create_bundle(src_path, dst_path.absolute())
    logger.info("done creating bundle of '%s' to '%s'", src_path, dst_path)


async def produce_archive_work(
        src_path: Path,
        dst_path: Path,
        options: ArchiverOptions,
        queue: asyncio.Queue):
    for repo_path in find_repos(src_path):
        if repo_path in options.skip_list:
            logger.info(
                "discovered '%s', but skipping as found in skip list", repo_path)
            continue

        repo_src_path = src_path / repo_path

        if await count_branches(repo_src_path) == 0:
            logger.info(
                "discovered '%s', but skipping as it has no branches", repo_path)
            continue

        logger.info("discovered '%s'", repo_path)

        repo_name = repo_src_path.stem
        repo_dst_path = dst_path / repo_path.parent / repo_name

        if not options.dry_run:
            logger.debug(
                "creating repo archive destination path at: '%s'", repo_dst_path)
            repo_dst_path.mkdir(parents=True, exist_ok=True)

        # archive HEAD
        await queue.put(WorkerTask(
            archive_repo,
            (
                repo_src_path,
                repo_dst_path /
                make_archive_name(repo_name, options.archive_type),
                "HEAD",
                options,
            ),
        ))

        # archive branches, if enabled
        if options.archive_branches:
            _, branches = await get_branches(repo_src_path)

            for branch in branches:
                await queue.put(WorkerTask(
                    archive_repo,
                    (
                        repo_src_path,
                        repo_dst_path / "branches" /
                        make_archive_name(branch, options.archive_type),
                        branch,
                        options,
                    ),
                ))

        # archive tags, if enabled
        if options.archive_tags:
            tags = await list_tags(repo_src_path)

            for tag in tags:
                await queue.put(WorkerTask(
                    archive_repo,
                    (
                        repo_src_path,
                        repo_dst_path / "tags" /
                        make_archive_name(tag, options.archive_type),
                        tag,
                        options,
                    ),
                ))

        # create git bundle, if enabled
        if options.create_bundle:
            bundle_dst = repo_dst_path / (repo_name + ".bundle")
            await queue.put(WorkerTask(
                archive_bundle,
                (
                    repo_src_path,
                    bundle_dst,
                    options,
                ),
            ))


async def archive_worker(name: str, queue: asyncio.Queue):
    while True:
        try:
            task: WorkerTask = await queue.get()
            await task.func(*task.args, **task.kwargs)
        finally:
            queue.task_done()


def create_archive_worker(i: int, queue: asyncio.Queue):
    return asyncio.create_task(archive_worker(f"worker-{i}", queue))


async def run_archiver(src_path: Path, dst_path: Path, options: ArchiverOptions):
    queue = asyncio.Queue()

    workers = [create_archive_worker(i, queue) for i in range(options.workers)]
    logger.debug("created %s workers", len(workers))

    # create archive work
    logger.debug("finding work")
    await produce_archive_work(src_path, dst_path, options, queue)

    # wait until queue is empty
    logger.debug("waiting for queue to empty")
    await queue.join()
    # stop all workers
    logger.debug("stopping all workers")
    for worker in workers:
        worker.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
