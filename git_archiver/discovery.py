from pathlib import Path


def find_repos(root_path: Path):
    """
    Discover git repositories from a given starting path.

    Args:
        root_path (Path): The path to search in

    Yields:
        Path: Each found repo, will be a relative to root
    """
    for path in root_path.rglob("*.git"):
        if path.is_dir():
            yield path.relative_to(root_path)
