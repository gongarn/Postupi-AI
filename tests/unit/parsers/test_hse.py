import json
from datetime import UTC, datetime

from packages.parsers.hse import HSE_NAMESPACE, HseParser, resolve_selection


def _fixture(*, mode: str = "registration") -> bytes:
    record = {
        "idEpgu": "private-applicant-1",
        "indexNumberInRegList": 1,
        "indexNumberInCompList": None if mode == "registration" else 1,
        "priority": 2,
        "isConcertToEnrollment": True,
        "isWithoutExamsAdmReasonBool": False,
        "withoutExamsAdmReason": "",
        "isAllScoresSatisfied": True,
        "participantStatus": "under_review",
        "sumCompetitiveScore": 350,
        "sumEntranceTestScore": 350,
        "achievementsSum": 10,
        "documentType": "passport",
    }
    return json.dumps(
        {
            "content": [record],
            "number": 0,
            "size": 50,
            "totalElements": 1,
            "totalPages": 1,
        }
    ).encode()


def _parser(*, mode: str = "registration") -> HseParser:
    return HseParser(
        uid_secret="unit-secret",
        campaign_year=2025,
        competitive_group_id="group-1",
        set_of_competitive_group_id="set-1",
        place_type="budget",
        level="bachelor",
        title="Computer Science",
        place_count=100,
        list_mode=mode,
    )


def test_hse_parser_normalizes_and_hmacs_identity() -> None:
    result = _parser().parse(
        _fixture(), source_url="https://example.invalid/applicant", fetched_at=datetime.now(UTC)
    )
    assert result.snapshot is not None
    application = result.snapshot.applications[0]
    assert application.identity_namespace == HSE_NAMESPACE.format(campaign_year=2025)
    assert application.applicant_uid_hmac != "private-applicant-1"
    assert "idEpgu" not in application.raw_payload
    assert "private-applicant-1" not in json.dumps(application.raw_payload)
    assert application.consent is True
    assert application.bvi is False
    assert result.snapshot.group.seat_counts == {"place_count": 100}


def test_hse_parser_accepts_competition_rank_only_in_competition_mode() -> None:
    result = _parser(mode="competition").parse(
        _fixture(mode="competition"),
        source_url="https://example.invalid/applicant",
        fetched_at=datetime.now(UTC),
    )
    assert result.status == "valid"
    assert result.snapshot is not None
    assert result.snapshot.applications[0].rank == 1


def test_hse_parser_rejects_missing_required_field() -> None:
    value = json.loads(_fixture())
    del value["content"][0]["priority"]
    result = _parser().parse(
        json.dumps(value).encode(),
        source_url="https://example.invalid/applicant",
        fetched_at=datetime.now(UTC),
    )
    assert result.status == "failed"


def test_hse_parser_rejects_unordered_ranks() -> None:
    value = json.loads(_fixture())
    value["content"].append(
        {
            **value["content"][0],
            "idEpgu": "private-applicant-2",
            "indexNumberInRegList": 1,
        }
    )
    result = _parser().parse(
        json.dumps(value).encode(),
        source_url="https://example.invalid/applicant",
        fetched_at=datetime.now(UTC),
    )
    assert result.status == "failed"


def test_hse_selection_is_derived_from_fresh_discovery() -> None:
    discovery = {
        "filials": [
            {
                "trainingDirections": [
                    {
                        "educationPrograms": [
                            {
                                "educationLevel": {"code": "bachelor"},
                                "competitiveGroups": [
                                    {
                                        "id": "fresh-group",
                                        "placeType": {"id": "fresh-place"},
                                        "setOfCompetitiveGroup": {"id": "fresh-set"},
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        ]
    }
    assert resolve_selection(json.dumps(discovery).encode()) == {
        "competitiveGroupId": "fresh-group",
        "setOfCompetitiveGroupId": "fresh-set",
        "placeType": "fresh-place",
        "level": "bachelor",
    }


def test_hse_selection_rejects_stale_or_incomplete_discovery() -> None:
    try:
        resolve_selection(b'{"filials": []}')
    except ValueError as exc:
        assert "no usable selection" in str(exc)
    else:
        raise AssertionError("incomplete discovery must be rejected")
