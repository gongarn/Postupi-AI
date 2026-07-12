import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from packages.parsers.hse import HseParser
from packages.parsers.hse_client import HseClient
from packages.parsers.storage import DiscardingRawSnapshotStorage, RawSnapshotMetadata


def test_hse_fresh_discovery_to_privacy_safe_normalization(tmp_path: Path) -> None:
    discovery = {
        "filials": [{
            "trainingDirections": [{"educationPrograms": [{
                "educationLevel": {"code": "bachelor"},
                "competitiveGroups": [{
                    "id": "fresh-group",
                    "placeType": {"id": "fresh-place"},
                    "setOfCompetitiveGroup": {"id": "fresh-set"},
                }],
            }]}]
        }]
    }
    applicants = {
        "content": [{
            "idEpgu": "private-applicant",
            "indexNumberInRegList": 1,
            "indexNumberInCompList": None,
            "priority": 1,
            "isConcertToEnrollment": True,
            "isWithoutExamsAdmReasonBool": False,
            "withoutExamsAdmReason": "",
            "isAllScoresSatisfied": True,
            "participantStatus": "under_review",
            "sumCompetitiveScore": 300,
            "sumEntranceTestScore": 290,
            "achievementsSum": 10,
            "documentType": "passport",
        }],
        "number": 0,
        "size": 50,
        "totalElements": 1,
        "totalPages": 1,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/competitve-group"):
            body = discovery
        elif request.url.path.endswith("/fresh-group"):
            body = {"placeCount": 10}
        else:
            body = applicants
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json=body,
        )

    async def fetch() -> bytes:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return (await HseClient(client).fetch_fresh_snapshot()).applicants

    content = asyncio.run(fetch())
    result = HseParser(
        uid_secret="integration-secret",
        campaign_year=2025,
        competitive_group_id="fresh-group",
        set_of_competitive_group_id="fresh-set",
        place_type="fresh-place",
        level="bachelor",
        title="Pilot",
        place_count=10,
        list_mode="registration",
    ).parse(content, source_url="https://example.invalid/hse", fetched_at=datetime.now(UTC))

    assert result.snapshot is not None
    application = result.snapshot.applications[0]
    serialized = json.dumps(result.snapshot, default=str)
    assert "private-applicant" not in serialized
    assert "idEpgu" not in application.raw_payload
    assert application.rank == 1
    assert result.snapshot.group.seat_counts == {"place_count": 10}

    body_hash = hashlib.sha256(content).hexdigest()
    storage = DiscardingRawSnapshotStorage()
    key = storage.put(
        content,
        metadata=RawSnapshotMetadata(
            source_url="https://example.invalid/hse",
            fetched_at=datetime.now(UTC).isoformat(),
            content_type="application/json",
            content_hash=body_hash,
            parser_version=result.snapshot.parser_version,
        ),
    )
    assert key.startswith("sha256/")
    assert list(tmp_path.iterdir()) == []
