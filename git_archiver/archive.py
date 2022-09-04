import logging
from dataclasses import dataclass
from pathlib import Path

from aiofiles import open as aio_open
from git_interface.archive import get_archive_buffered
from git_interface.branch import count_branches, get_branches
from git_interface.datatypes import ArchiveTypes
from git_interface.tag import list_tags

from .discovery import find_repos

logger = logging.getLogger("archiver")


@dataclass
class ArchiverOptions:
    archive_type: ArchiveTypes
    dry_run: bool = False
    archive_branches: bool = False
    archive_tags: bool = False


def make_archive_name(name: str, archive_type: ArchiveTypes) -> str:
    return f"{name}.{archive_type.value}"


async def archive_repo(src_path: Path, dst_path: Path, tree_ish: str, options: ArchiverOptions):
    if options.dry_run:
        _ = [_ async for _ in get_archive_buffered(src_path, options.archive_type, tree_ish)]
        return

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    async with aio_open(dst_path, "wb") as fo:
        async for chunk in get_archive_buffered(src_path, options.archive_type, tree_ish):
            await fo.write(chunk)


async def archive_repos(src_path: Path, dst_path: Path, options: ArchiverOptions):
    for repo_path in find_repos(src_path):
        repo_src_path = src_path / repo_path

        if await count_branches(repo_src_path) == 0:
            logger.info("skipping '%s' as it has no branches", repo_path)
            continue

        repo_name = repo_src_path.stem
        repo_dst_path = dst_path / repo_path.parent / repo_name

        logger.info(
            "started archiving '%s' to '%s'",
            repo_path, repo_dst_path,
        )

        await archive_repo(
            repo_src_path,
            repo_dst_path / make_archive_name(repo_name, options.archive_type),
            "HEAD",
            options,
        )

        if options.archive_branches:
            _, branches = await get_branches(repo_src_path)

            for branch in branches:
                await archive_repo(
                        repo_src_path,
                        repo_dst_path / "branches" / make_archive_name(branch, options.archive_type),
                        branch,
                        options,
                    )

        if options.archive_tags:
            tags = await list_tags(repo_src_path)

            for tag in tags:
                await archive_repo(
                        repo_src_path,
                        repo_dst_path / "tags" / make_archive_name(tag, options.archive_type),
                        tag,
                        options,
                    )

        logger.info("done archiving '%s' to '%s'", repo_path, repo_dst_path)
