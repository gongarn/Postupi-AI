import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.parsers.itmo import ITMO_SOURCE_URL, ItmoParser


@pytest.mark.private_fixture
def test_private_itmo_fixture_aggregate_only() -> None:
    path_value = os.environ.get("POSTUPI_ITMO_FIXTURE_PATH")
    if not path_value:
        pytest.skip("POSTUPI_ITMO_FIXTURE_PATH is not configured")
    path = Path(path_value)
    if not path.is_file():
        pytest.skip("private ITMO fixture is unavailable")
    result = ItmoParser(uid_secret="private-fixture-test-secret").parse(
        path.read_bytes(), source_url=ITMO_SOURCE_URL, fetched_at=datetime.now(UTC)
    )
    assert result.snapshot is not None
    assert result.status == "valid"
    assert len(result.snapshot.applications) > 0
    assert len({item.applicant_uid_hmac for item in result.snapshot.applications}) > 0
