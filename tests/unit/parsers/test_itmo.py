import json
from datetime import UTC, datetime

from packages.parsers.itmo import ITMO_NAMESPACE, ItmoParser


def _fixture() -> bytes:
    record = {
        "disciplines_scores": {"math": 80},
        "exam_scores": 240,
        "exam_type": "ege",
        "has_approved_contract": False,
        "highest_passageway_priority": True,
        "ia_scores": 10,
        "is_detailed_target_quota": None,
        "is_have_advantages": False,
        "is_published_in_work_in_russia": None,
        "is_send_agreement": True,
        "is_special_b_category": None,
        "link": "/private/12345",
        "main_top_priority": True,
        "offer_number": None,
        "olympiad": None,
        "position": 2,
        "priority": 1,
        "sspvo_id": "12345",
        "status": "recommended",
        "target_achievements": None,
        "target_organization_number": None,
        "total_scores": 250,
    }
    page = {
        "degree": "bachelor",
        "financing": "budget",
        "programList": {
            "direction": {"competitive_group_id": 2199, "direction_title": "Information Security"},
            "general_competition": [record],
            "by_special_quota": [],
            "by_target_quota": [],
            "by_unusual_quota": [],
            "without_entry_tests": [],
        },
    }
    value = {"query": {"id": "2199"}, "props": {"pageProps": page}}
    return f'<script id="__NEXT_DATA__">{json.dumps(value)}</script>'.encode()


def test_itmo_parser_allowlist_and_hmac() -> None:
    raw_uid = "12345"
    result = ItmoParser(uid_secret="unit-secret").parse(
        _fixture(), source_url="https://example.invalid", fetched_at=datetime.now(UTC)
    )
    assert result.snapshot is not None
    assert result.status == "valid"
    application = result.snapshot.applications[0]
    assert application.identity_namespace == ITMO_NAMESPACE
    assert application.applicant_uid_hmac != raw_uid
    assert "sspvo_id" not in application.raw_payload
    assert "link" not in application.raw_payload
    assert raw_uid not in json.dumps(application.raw_payload)


def test_itmo_parser_rejects_schema_drift() -> None:
    payload = json.loads(_fixture().decode().split(">", 1)[1].rsplit("<", 1)[0])
    payload["props"]["pageProps"]["programList"]["general_competition"][0]["new_field"] = True
    content = f'<script id="__NEXT_DATA__">{json.dumps(payload)}</script>'.encode()
    result = ItmoParser(uid_secret="unit-secret").parse(
        content, source_url="https://example.invalid", fetched_at=datetime.now(UTC)
    )
    assert result.status == "failed"
