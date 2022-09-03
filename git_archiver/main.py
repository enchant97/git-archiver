import argparse
import logging
from pathlib import Path

from git_interface.datatypes import ArchiveTypes

from .archive import archive_repo, create_archive_path
from .discovery import find_repos


async def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser("git_archiver", description="Designed to make archiving git bare repositories easy.")
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

    found_repos = find_repos(args.src)

    for repo_path in found_repos:
        src_path = args.src / repo_path
        dst_path = create_archive_path(args.dst, repo_path, args.format)
        logging.info("started archiving '%s' to '%s'", repo_path, dst_path)
        await archive_repo(src_path, dst_path, args.format, dry_run=args.dry_run)
        logging.info("done archiving '%s' to '%s'", repo_path, dst_path)
