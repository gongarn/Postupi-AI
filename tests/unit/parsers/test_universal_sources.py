from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.parsers.fa import FaParser
from packages.parsers.misis import MisisParser
from packages.parsers.mpei import MpeiParser
from packages.parsers.msu import MsuSectionParser, split_sections
from packages.parsers.rnimu import RnimuParser
from packages.parsers.rudn import RudnParser
from packages.parsers.sechenov import SechenovParser
from packages.parsers.stankin import StankinParser

PRIVATE_FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "private"


def _fixture(name: str) -> bytes:
    path = PRIVATE_FIXTURES / name
    if not path.is_file():
        pytest.skip(f"private fixture {name} is unavailable")
    return path.read_bytes()


def _parse(parser: object, content: bytes, url: str) -> object:
    return parser.parse(content, source_url=url, fetched_at=datetime.now(UTC))


def _assert_valid(result: object, *, expected_min: int = 1) -> None:
    assert result.status == "valid"
    assert result.snapshot is not None
    assert len(result.snapshot.applications) >= expected_min
    uids = {item.applicant_uid_hmac for item in result.snapshot.applications}
    assert len(uids) == len(result.snapshot.applications)


@pytest.mark.private_fixture
def test_rnimu_fixture() -> None:
    result = _parse(
        RnimuParser(uid_secret="test-secret"),
        _fixture("rnimu_lechebnoe.json"),
        "https://ratings.rsmu.ru/data/p3_85648.json",
    )
    _assert_valid(result, expected_min=100)
    assert result.snapshot.group.university_code == "rnimu"
    assert result.snapshot.group.seat_counts is not None
    sample = result.snapshot.applications[0]
    assert sample.enrollment_priority is not None or sample.competitive_score is not None


@pytest.mark.private_fixture
def test_mpei_fixture() -> None:
    result = _parse(
        MpeiParser(uid_secret="test-secret", group_id="4bac", title="4bac"),
        _fixture("mpei_list4bacc.html"),
        "https://pk.mpei.ru/inform/list4bacc.html",
    )
    _assert_valid(result, expected_min=100)


@pytest.mark.private_fixture
def test_misis_fixture() -> None:
    result = _parse(
        MisisParser(uid_secret="test-secret", group_id="bvo-1", title="bvo-1"),
        _fixture("misis_bvo_budj.html"),
        "https://misis.ru/.../list/?id=BVO-BUDJ",
    )
    _assert_valid(result, expected_min=50)


@pytest.mark.private_fixture
def test_fa_fixture() -> None:
    result = _parse(
        FaParser(uid_secret="test-secret"),
        _fixture("fa_listabit.html"),
        "https://www.fa.ru/spiski/listabit.php",
    )
    _assert_valid(result, expected_min=10)


@pytest.mark.private_fixture
def test_stankin_fixture() -> None:
    result = _parse(
        StankinParser(
            uid_secret="test-secret",
            group_id="bs-09.03.01",
            title="09.03.01 Информатика и вычислительная техника",
            financing="budget",
        ),
        _fixture("stankin_grid.html"),
        "https://priem.stankin.ru/gridspisokpostupayushchikh",
    )
    _assert_valid(result, expected_min=10)
    assert any(item.application_status for item in result.snapshot.applications)


@pytest.mark.private_fixture
def test_msu_fixture_sections() -> None:
    page = _fixture("msu_vmk_2026.html").decode("utf-8", errors="replace")
    sections = split_sections(page)
    assert len(sections) >= 5
    assert any(section.seat_count is not None for section in sections)
    # секция с таблицей (конкурсная), лучше — общий конкурс
    section = next(
        (s for s in sections if "<table" in s.html and s.condition == "general_competition"),
        next((s for s in sections if "<table" in s.html), None),
    )
    assert section is not None
    result = _parse(
        MsuSectionParser(uid_secret="test-secret", section=section, faculty_code="dep_02"),
        section.html.encode("utf-8"),
        f"https://cpk.msu.ru/rating/dep_02#{section.anchor_id}",
    )
    _assert_valid(result, expected_min=50)


@pytest.mark.private_fixture
def test_rudn_fixture() -> None:
    result = _parse(
        RudnParser(uid_secret="test-secret", group_id="8417363", title="8417363"),
        _fixture("rudn_fmien_2026.html"),
        "https://admission.rudn.ru/undergraduate/competition_list/8417363/",
    )
    _assert_valid(result, expected_min=5)


@pytest.mark.private_fixture
def test_sechenov_fixture() -> None:
    result = _parse(
        SechenovParser(uid_secret="test-secret", group_id="19491", title="19491"),
        _fixture("sechenov_19491.html"),
        "https://priem.sechenov.ru/.../applications.php",
    )
    _assert_valid(result, expected_min=5)


@pytest.mark.private_fixture
def test_gubkin_fixture() -> None:
    from packages.parsers.gubkin import GubkinParser

    result = _parse(
        GubkinParser(uid_secret="test-secret", group_id="2443", title="Конкурсная группа 5"),
        _fixture("gubkin_group_2443.json"),
        "https://transfer.priem.gubkin.ru/.../api.php?method=get",
    )
    _assert_valid(result, expected_min=100)
    assert any(item.consent is not None for item in result.snapshot.applications)
