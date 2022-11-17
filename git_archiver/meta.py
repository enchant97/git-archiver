import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from git_interface.datatypes import ArchiveTypes, Log

from . import __version__

PRODUCED_WITH_VALUE = f"git-archiver-{__version__}"


class ArchiveMetaJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ArchiveTypes):
            return obj.value
        elif isinstance(obj, datetime):
            return obj.isoformat()


@dataclass
class ArchiveMetaTree:
    commit_date: datetime
    commit_hash: str
    parent_hash: str

    @classmethod
    def from_log(cls, log: Log):
        return cls(
            commit_date=log.commit_date,
            commit_hash=log.commit_hash,
            parent_hash=log.parent_hash,
        )

    def asdict(self):
        return asdict(self)


@dataclass
class ArchiveMeta:
    name: str
    archive_type: ArchiveTypes
    has_bundle: bool = False
    head: ArchiveMetaTree | None = None
    branches: dict[str, ArchiveMetaTree] = field(default_factory=dict)
    tags: dict[str, ArchiveMetaTree] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    produced_with: str = PRODUCED_WITH_VALUE

    def asdict(self):
        return asdict(self)

    def dumps(self) -> str:
        return json.dumps(self.asdict(), indent=4, cls=ArchiveMetaJSONEncoder)
