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


async def archive_repository(
        root_path: Path,
        src_path: Path,
        dst_path: Path,
        options: ArchiverOptions):
    if await count_branches(src_path) == 0:
        logger.info(
            "skipping '%s', as it has no branches", src_path)
        return

    repo_name = src_path.stem
    repo_dst_path = dst_path / src_path.relative_to(root_path)

    if not options.dry_run:
        logger.debug(
            "creating repo archive destination path at: '%s'", repo_dst_path)
        repo_dst_path.mkdir(parents=True, exist_ok=True)

    # archive HEAD
    await archive_repo(
        src_path,
        repo_dst_path /
        make_archive_name(repo_name, options.archive_type),
        "HEAD",
        options,
    )

    # archive branches, if enabled
    if options.archive_branches:
        _, branches = await get_branches(src_path)

        for branch in branches:
            await archive_repo(
                src_path,
                repo_dst_path / "branches" /
                make_archive_name(branch, options.archive_type),
                branch,
                options,
            )

    # archive tags, if enabled
    if options.archive_tags:
        tags = await list_tags(src_path)

        for tag in tags:
            await archive_repo(
                src_path,
                repo_dst_path / "tags" /
                make_archive_name(tag, options.archive_type),
                tag,
                options,
            )

    # create git bundle, if enabled
    if options.create_bundle:
        bundle_dst = repo_dst_path / (repo_name + ".bundle")
        await archive_bundle(
            src_path,
            bundle_dst,
            options,
        )


class ArchiverHandler:
    __work_queue: asyncio.Queue
    __workers: list
    __accept_work: bool = False

    _root_path: Path
    _dst_path: Path
    _options: ArchiverOptions

    def __init__(self, root_path: Path, dst_path: Path, options: ArchiverOptions):
        self.__work_queue = asyncio.Queue()
        self._root_path = root_path
        self._dst_path = dst_path
        self._options = options

    async def __worker_func(self, worker_name: str):
        while True:
            try:
                src_path: Path = await self.__work_queue.get()
                logger.debug("'%s' starting work on '%s'",
                             worker_name, src_path)
                await archive_repository(self._root_path, src_path, self._dst_path, self._options)
                logger.debug("'%s' completed work on '%s'",
                             worker_name, src_path)
            finally:
                self.__work_queue.task_done()

    def __create_worker(self, i: int):
        return asyncio.create_task(self.__worker_func(f"archive-worker-{i}"))

    async def push_repo(self, src_path: Path):
        """
        Add a new repo to archive from the file system
        """
        if not self.__accept_work:
            # HACK Make custom exception!
            raise Exception("archiver is no longer accepting work")

        await self.__work_queue.put(src_path)

    def start(self):
        if self.__accept_work:
            # HACK Make custom exception!
            raise Exception("archiver has already been started")

        self.__accept_work = True
        self.__workers = [self.__create_worker(i)
                          for i in range(self._options.workers)]
        logger.debug("created %s workers", len(self.__workers))

    async def stop(self):
        """
        Shuts down the archiver safely, will wait for all tasks to complete
        """
        self.__accept_work = False

        logger.debug("waiting for queue to empty")
        await self.__work_queue.join()

        logger.debug("stopping all workers")
        for worker in self.__workers:
            worker.cancel()
        await asyncio.gather(*self.__workers, return_exceptions=True)

        self.__workers = None
