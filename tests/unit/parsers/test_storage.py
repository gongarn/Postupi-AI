import hashlib
from pathlib import Path

from packages.parsers.storage import DiscardingRawSnapshotStorage, RawSnapshotMetadata


def test_discarding_storage_does_not_write_response_body(tmp_path: Path) -> None:
    content = b'{"content": []}'
    content_hash = hashlib.sha256(content).hexdigest()
    key = DiscardingRawSnapshotStorage().put(
        content,
        metadata=RawSnapshotMetadata(
            source_url="https://example.invalid",
            fetched_at="2025-01-01T00:00:00+00:00",
            content_type="application/json",
            content_hash=content_hash,
            parser_version="hse-json-1",
        ),
    )
    assert key == f"sha256/{content_hash[:2]}/{content_hash}"
    assert list(tmp_path.iterdir()) == []
