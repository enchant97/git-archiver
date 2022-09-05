import argparse
import logging
from pathlib import Path

from git_interface.datatypes import ArchiveTypes

from .archive import ArchiverOptions, archive_repos

logger = logging.getLogger("cli")


async def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(
        "git_archiver",
        usage="option [options ...]",
        description="Designed to make archiving git bare repositories easy.",
    )
    parser.add_argument(
        "--src", help="Path to directory of git repositories", type=Path, required=True)
    parser.add_argument(
        "--dst", help="Path to directory where the archive will be created", type=Path, required=True)
    parser.add_argument(
        "--format", help="What format to use for archive (tar is default)",
        default=ArchiveTypes.TAR,
        type=ArchiveTypes,
        choices=[type_.value for type_ in ArchiveTypes],
    )
    parser.add_argument(
        "--branches", help="Archive all branches", action="store_true")
    parser.add_argument("--tags", help="Archive all tags", action="store_true")
    parser.add_argument(
        "-n", "--dry-run", help="Run archiver without doing the actual archive", action="store_true")
    parser.add_argument(
        "--bundle", help="Create git bundles for each repository", action="store_true")
    parser.add_argument(
        "--skip", help="Add paths of repository directories to skip, " +
        "must be relative the src", nargs="+", type=Path, default=[])

    args = parser.parse_args()

    options = ArchiverOptions(
        archive_type=args.format,
        dry_run=args.dry_run,
        archive_branches=args.branches,
        archive_tags=args.tags,
        create_bundle=args.bundle,
        skip_list=args.skip,
    )

    logger.info("archiver starting")
    await archive_repos(args.src, args.dst, options)
    logger.info("archiver finished")
