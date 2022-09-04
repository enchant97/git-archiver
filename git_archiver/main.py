import argparse
import logging
from pathlib import Path

from git_interface.datatypes import ArchiveTypes

from .archive import ArchiverOptions, archive_repos


async def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        "git_archiver", description="Designed to make archiving git bare repositories easy.")
    parser.add_argument(
        "--src", help="where the git repos are", type=Path, required=True)
    parser.add_argument(
        "--dst", help="where to store archives", type=Path, required=True)
    parser.add_argument(
        "--format", help="what format to use for archive",
        default=ArchiveTypes.TAR,
        type=ArchiveTypes,
        choices=[type_.value for type_ in ArchiveTypes],
    )
    parser.add_argument(
        "-n", "--dry-run", help="run archiver without doing the actual archive", action="store_true")

    args = parser.parse_args()

    options = ArchiverOptions(
        archive_type=args.format,
        dry_run=args.dry_run,
    )

    await archive_repos(args.src, args.dst, options)
