from __future__ import annotations

import httpx

from packages.parsers import universal_fetchers as fetchers
from packages.parsers.fa import FaParser
from packages.parsers.itmo import ItmoParser
from packages.parsers.misis import MisisParser
from packages.parsers.mpei import MpeiParser
from packages.parsers.msu import MsuSectionParser
from packages.parsers.registry import SOURCES, FetchedDocument, UniversitySource
from packages.parsers.rnimu import RnimuParser
from packages.parsers.rudn import RudnParser
from packages.parsers.sechenov import SechenovParser
from packages.parsers.stankin import StankinParser


def _register() -> None:
    # ИТМО — основной источник с собственным batch-ингейшеном;
    # в реестре только для прогнозного гейта (enabled=False — не фетчим дважды).
    SOURCES["itmo"] = UniversitySource(
        code="itmo",
        name="ИТМО",
        parser=ItmoParser,
        fetcher=_disabled_fetcher,
        forecast_eligible=True,
        enabled=False,
    )
    SOURCES["rnimu"] = UniversitySource(
        code="rnimu",
        name="РНИМУ им. Н.И. Пирогова",
        parser=RnimuParser,
        fetcher=fetchers.fetch_rnimu,
    )
    SOURCES["mpei"] = UniversitySource(
        code="mpei",
        name="НИУ МЭИ",
        parser=MpeiParser,
        fetcher=fetchers.fetch_mpei,
    )
    SOURCES["misis"] = UniversitySource(
        code="misis",
        name="НИТУ МИСИС",
        parser=MisisParser,
        fetcher=fetchers.fetch_misis,
    )
    SOURCES["fa"] = UniversitySource(
        code="fa",
        name="Финансовый университет при Правительстве РФ",
        parser=FaParser,
        fetcher=fetchers.fetch_fa,
    )
    SOURCES["stankin"] = UniversitySource(
        code="stankin",
        name="МГТУ СТАНКИН",
        parser=StankinParser,
        fetcher=fetchers.fetch_stankin,
    )
    SOURCES["msu"] = UniversitySource(
        code="msu",
        name="МГУ им. М.В. Ломоносова",
        parser=MsuSectionParser,
        fetcher=fetchers.fetch_msu,
        refresh_minutes=180,
    )
    SOURCES["rudn"] = UniversitySource(
        code="rudn",
        name="РУДН",
        parser=RudnParser,
        fetcher=fetchers.fetch_rudn,
    )
    SOURCES["sechenov"] = UniversitySource(
        code="sechenov",
        name="Первый МГМУ им. И.М. Сеченова",
        parser=SechenovParser,
        fetcher=fetchers.fetch_sechenov,
    )


_register()


async def _disabled_fetcher(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    raise NotImplementedError("ITMO uses its own batch ingestion")
