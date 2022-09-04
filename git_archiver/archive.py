import logging
from dataclasses import dataclass
from pathlib import Path

from aiofiles import open as aio_open
from git_interface.archive import get_archive_buffered
from git_interface.datatypes import ArchiveTypes

from .discovery import find_repos

logger = logging.getLogger("archiver")


@dataclass
class ArchiverOptions:
    archive_type: ArchiveTypes
    dry_run: bool = False


def create_archive_path(dst_path: Path, repo_path: Path, archive_type: ArchiveTypes) -> Path:
    return dst_path / repo_path.parent / (repo_path.name + "." + archive_type.value)


async def archive_repo(src_path: Path, dst_path: Path, options: ArchiverOptions):
    if options.dry_run:
        _ = [_ async for _ in get_archive_buffered(src_path, options.archive_type)]
        return

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    async with aio_open(dst_path, "wb") as fo:
        async for chunk in get_archive_buffered(src_path, options.archive_type):
            await fo.write(chunk)


async def archive_repos(src_path: Path, dst_path: Path, options: ArchiverOptions):
    for repo_path in find_repos(src_path):
        repo_src_path = src_path / repo_path
        repo_dst_path = create_archive_path(
            dst_path,
            repo_path,
            options.archive_type,
        )

        logging.info(
            "started archiving '%s' to '%s'",
            repo_path, repo_dst_path,
        )

        await archive_repo(repo_src_path, repo_dst_path, options)

        logging.info("done archiving '%s' to '%s'", repo_path, repo_dst_path)
