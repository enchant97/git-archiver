import logging
from pathlib import Path

from .exceptions import PathNotAbsolute

logger = logging.getLogger("discovery")


class FileSystemDiscovery:
    """
    Discover git repositories inside given root path
    """
    def __init__(self, root_path: Path, skip_list: list | None = None):
        if not root_path.is_absolute():
            raise PathNotAbsolute("root_path must be a absolute path")

        if skip_list is None:
            skip_list = []
        self._root_path = root_path
        self._skip_list = skip_list

    def __find_repos(self):
        for path in self._root_path.rglob("*.git"):
            if path.is_dir() and path not in self._skip_list:
                logger.debug("found '%s'", path)
                yield path.resolve()

    def discover(self):
        """
        Yields discovered repository paths, will be absolute
        """
        return self.__find_repos()
