from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawSnapshotMetadata:
    source_url: str
    fetched_at: str
    content_type: str
    content_hash: str
    parser_version: str


class RawSnapshotStorage:
    def put(self, content: bytes, *, metadata: RawSnapshotMetadata) -> str:
        raise NotImplementedError


class LocalContentAddressedRawSnapshotStorage(RawSnapshotStorage):
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, content: bytes, *, metadata: RawSnapshotMetadata) -> str:
        content_hash = hashlib.sha256(content).hexdigest()
        if content_hash != metadata.content_hash:
            raise ValueError("raw content hash mismatch")
        relative = Path("sha256") / content_hash[:2] / f"{content_hash}.html"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(content)
        return relative.as_posix()
