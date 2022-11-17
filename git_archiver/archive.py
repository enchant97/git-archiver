import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from aiofiles import open as aio_open
from git_interface.archive import get_archive_buffered
from git_interface.branch import count_branches, get_branches
from git_interface.datatypes import ArchiveTypes
from git_interface.exceptions import GitException
from git_interface.helpers import subprocess_run
from git_interface.log import get_logs
from git_interface.tag import list_tags

from .exceptions import ArchiverRunning, ArchiverStopped
from .meta import ArchiveMeta, ArchiveMetaTree

logger = logging.getLogger("archiver")


@dataclass
class ArchiverOptions:
    archive_type: ArchiveTypes
    archive_branches: bool = False
    archive_tags: bool = False
    create_bundle: bool = False
    skip_list: list = field(default_factory=list),
    workers: int = 3,


# TODO use git-interface implementation, when available
async def create_bundle(git_repo: Path, dst_path: Path):
    args = ["git", "-C", str(git_repo), "bundle",
            "create", str(dst_path), "--all"]
    process_status = await subprocess_run(args)
    if process_status.returncode != 0:
        stderr = process_status.stderr.decode()
        raise GitException(stderr)


class RepositoryArchiver:
    """
    Archive a single repository,
    using given options to determine what gets archived
    """
    _root_path: Path
    _src_path: Path
    _dst_path: Path
    _options: ArchiverOptions

    _repo_name: str
    _repo_dst_path: Path
    _archive_meta: ArchiveMeta

    def __init__(
            self,
            root_path: Path,
            src_path: Path,
            dst_path: Path,
            options: ArchiverOptions):
        """
        Args:
            root_path (Path): The root path
            src_path (Path): The absolute path to the repo
            dst_path (Path): Root path to store archives
            options (ArchiverOptions): Archive settings
        """
        self._root_path = root_path
        self._src_path = src_path
        self._dst_path = dst_path
        self._options = options

        self._repo_name = self._src_path.stem
        self._repo_dst_path = self._dst_path / \
            self._src_path.relative_to(self._root_path).with_suffix("")

        self._archive_meta = ArchiveMeta(
            name=self._repo_name,
            archive_type=self._options.archive_type,
        )

    def make_archive_name(self, name: str) -> str:
        """
        Create an archive base name.

        Args:
            name (str): The name of the archive

        Returns:
            str: The full archive name
        """
        return f"{name}.{self._options.archive_type.value}"

    async def get_tree_meta(self, tree_ish: str | None = None) -> ArchiveMetaTree:
        """
        Get a repositories tree metadata, defaults to HEAD

        Args:
            tree_ish (str | None, optional): The tree-ish to use. Defaults to None.

        Returns:
            ArchiveMetaTree: The created metadata
        """
        log = next(await get_logs(self._src_path, branch=tree_ish, max_number=1))
        return ArchiveMetaTree.from_log(log)

    async def _archive_tree(self, dst_path: Path, tree_ish: str):
        """
        Produces an archive from the given tree-ish

        Args:
            dst_path (Path): Where to store the archive
            tree_ish (str): The tree-ish to archive
        """
        logger.debug(
            "started archiving '%s' to '%s' at '%s'",
            self._src_path, dst_path, tree_ish,
        )

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        async with aio_open(dst_path, "wb") as fo:
            async for chunk in get_archive_buffered(
                    self._src_path,
                    self._options.archive_type,
                    tree_ish,
            ):
                await fo.write(chunk)

        logger.debug(
            "done archiving '%s' to '%s' at '%s'",
            self._src_path, dst_path, tree_ish,
        )

    async def _archive_head(self):
        """
        Produces archive of HEAD branch in the repository
        """
        await self._archive_tree(
            self._repo_dst_path / self.make_archive_name("HEAD"),
            "HEAD",
        )
        self._archive_meta.head = await self.get_tree_meta()

    async def _archive_branches(self):
        """
        Produces archives of all branches (apart from the HEAD) in the repository
        """
        _, branches = await get_branches(self._src_path)

        for branch in branches:
            await self._archive_tree(
                self._repo_dst_path / "branches" /
                self.make_archive_name(branch),
                branch,
            )
            self._archive_meta.branches[branch] = await self.get_tree_meta(branch)

    async def _archive_tags(self):
        """
        Produces archives of all tags in the repository
        """
        tags = await list_tags(self._src_path)

        for tag in tags:
            await self._archive_tree(
                self._repo_dst_path / "tags" / self.make_archive_name(tag),
                tag,
            )
            self._archive_meta.tags[tag] = await self.get_tree_meta(tag)

    async def _archive_bundle(self):
        """
        Produces a git-bundle of the repository
        """
        bundle_dst = self._repo_dst_path / "all.bundle"

        await create_bundle(self._src_path, bundle_dst.absolute())
        self._archive_meta.has_bundle = True

    async def _write_meta(self):
        """
        Write the archive metadata file, called on completion
        """
        async with aio_open(self._repo_dst_path / "meta.json", "wt") as fo:
            await fo.write(self._archive_meta.dumps())

    async def archive(self):
        """
        Start archiving the set src repository into the set dst path
        """
        if await count_branches(self._src_path) == 0:
            logger.info(
                "skipping '%s', as it has no branches", self._src_path)
            return

        logger.debug(
            "creating repo archive destination path at: '%s'", self._repo_dst_path)
        self._repo_dst_path.mkdir(parents=True, exist_ok=True)

        logger.info("archiving HEAD of '%s'", self._src_path)
        await self._archive_head()

        if self._options.archive_branches:
            logger.info("archiving branches of '%s'", self._src_path)
            await self._archive_branches()

        if self._options.archive_tags:
            logger.info("archiving tags of '%s'", self._src_path)
            await self._archive_tags()

        if self._options.create_bundle:
            logger.info("archiving bundle of '%s'", self._src_path)
            await self._archive_bundle()

        await self._write_meta()


class ArchiverHandler:
    """
    Archive handler that will archive multiple repositories
    """
    __work_queue: asyncio.Queue
    __workers: list
    __accept_work: bool = False

    _root_path: Path
    _dst_path: Path
    _options: ArchiverOptions

    def __init__(self, root_path: Path, dst_path: Path, options: ArchiverOptions):
        """
        Args:
            root_path (Path): The root path
            dst_path (Path): The absolute path to the repo
            options (ArchiverOptions): Archive settings
        """
        self.__work_queue = asyncio.Queue()
        self._root_path = root_path
        self._dst_path = dst_path
        self._options = options

    async def __worker_func(self, worker_name: str):
        logger.debug("'%s' waiting for work", worker_name)
        try:
            while True:
                src_path: Path = await self.__work_queue.get()
                logger.debug("'%s' starting work on '%s'",
                             worker_name, src_path)
                repo_archiver = RepositoryArchiver(
                    self._root_path,
                    src_path,
                    self._dst_path,
                    self._options,
                )
                await repo_archiver.archive()
                logger.debug("'%s' completed work on '%s'",
                             worker_name, src_path)
                self.__work_queue.task_done()
        except asyncio.exceptions.CancelledError:
            pass
        finally:
            logger.debug("'%s' stopping", worker_name)

    def __create_worker(self, i: int):
        return asyncio.create_task(self.__worker_func(f"archive-worker-{i}"))

    async def push_repo(self, src_path: Path):
        """
        Add a new repo to archive from the file system

        Args:
            src_path (Path): The absolute path pointing to the repo,
                             must be relative to the given root path

        Raises:
            ArchiverStopped: The archiver has been stopped,
                             so new work cannot be added
        """
        if not self.__accept_work:
            raise ArchiverStopped("archiver is no longer accepting work")

        await self.__work_queue.put(src_path)

    def start(self):
        """
        Start the archiver, launches the async task workers

        Raises:
            ArchiverRunning: Archiver start method has already been called
        """
        if self.__accept_work:
            raise ArchiverRunning("archiver has already been started")

        self.__accept_work = True
        self.__workers = [self.__create_worker(i)
                          for i in range(self._options.workers)]
        logger.debug("created %s workers", len(self.__workers))

    async def stop(self):
        """
        Stop the archiver, will wait for all tasks to complete

        Raises:
            ArchiverStopped: The archiver stop method has already been called
        """
        if self.__accept_work is False:
            raise ArchiverStopped(
                "archiver has already been stopped, or was never started")

        # ensure no new jobs get added
        self.__accept_work = False

        logger.debug("waiting for queue to empty")
        await self.__work_queue.join()

        logger.debug("stopping all workers")
        for worker in self.__workers:
            worker.cancel()
        await asyncio.gather(*self.__workers, return_exceptions=False)

        # remove references for async tasks, (can be collected by garbage collector)
        self.__workers = None
