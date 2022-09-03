from pathlib import Path

from aiofiles import open as aio_open
from git_interface.datatypes import ArchiveTypes
from git_interface.utils import get_archive_buffered


def create_archive_path(dst_path: Path, repo_path: Path, archive_type: ArchiveTypes) -> Path:
    return dst_path / repo_path.parent / (repo_path.name + "." + archive_type.value)


async def archive_repo(src_path: Path, dst_path: Path, archive_type: ArchiveTypes, /, *, dry_run: bool = False):
    if dry_run:
        _ = [_ async for _ in get_archive_buffered(src_path, archive_type)]
        return

    dst_path.parent.mkdir(parents=True, exist_ok=True)

    async with aio_open(dst_path, "wb") as fo:
        async for chunk in get_archive_buffered(src_path, archive_type):
            await fo.write(chunk)
