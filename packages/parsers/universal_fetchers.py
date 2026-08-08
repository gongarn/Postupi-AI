from __future__ import annotations

import asyncio
import json
import re
from html import unescape
from urllib.parse import quote, urljoin

import httpx

from packages.parsers.fetchers import fetch_document
from packages.parsers.registry import FetchedDocument

RNIMU_ROOT = "https://ratings.rsmu.ru/data/root.json"
MPEI_INDEX = "https://pk.mpei.ru/inform/list"
MISIS_INDEX = (
    "https://misis.ru/applicants/admission/progress/"
    "baccalaureate-and-specialties/list-of-applicants/"
)
FA_URL = "https://www.fa.ru/spiski/listabit.php?id_filial=0&type_list=%D0%B1%D0%BA%D0%BB"
STANKIN_INDEX = "https://priem.stankin.ru/bakalavriatispetsialitet/ranked-lists/"
STANKIN_GRID = "https://priem.stankin.ru/gridspisokpostupayushchikh"
MSU_RATING = "https://cpk.msu.ru/rating"
RUDN_INDEX = "https://admission.rudn.ru/undergraduate/competition_list/"
SECHENOV_INDEX = "https://priem.sechenov.ru/admission-lists/"
SECHENOV_API = (
    "https://priem.sechenov.ru/local/components/firstbit/competition.list/"
    "templates/.default/applications.php"
)


async def fetch_rnimu(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    root = await fetch_document(RNIMU_ROOT, client=client, content_type="application/json")
    campaigns = json.loads(root.content)
    selected: str | None = None
    for campaign in campaigns:
        if "специалитет" in str(campaign.get("title", "")).lower():
            selected = str(campaign["file"])
            break
    if selected is None:
        return ()
    versions = json.loads(
        (await fetch_document(
            f"https://ratings.rsmu.ru/data/{selected}", client=client
        )).content
    )
    if not versions:
        return ()
    groups = json.loads(
        (await fetch_document(
            f"https://ratings.rsmu.ru/data/{versions[0]['file']}", client=client
        )).content
    )
    documents: list[FetchedDocument] = []
    for group in groups:
        url = f"https://ratings.rsmu.ru/data/{group['file']}"
        doc = await fetch_document(url, client=client, content_type="application/json")
        documents.append(
            FetchedDocument(
                content=doc.content,
                source_url=url,
                content_type="application/json",
            )
        )
    return tuple(documents)


async def fetch_mpei(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    index = await fetch_document(MPEI_INDEX, client=client)
    html = index.content.decode("utf-8", errors="replace")
    # строки таблицы: ячейка с названием направления + ссылки на списки
    titles: dict[str, str] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) < 2:
            continue
        name = unescape(re.sub(r"<[^>]+>", " ", cells[0]))
        name = re.sub(r"\s+", " ", name).strip()
        if not name:
            continue
        for href in re.findall(r'href="([^"]+)"', cells[1]):
            if re.search(r"/inform/list\d+bacc\.html$", href):
                titles[href] = name
    hrefs = sorted(titles)
    documents: list[FetchedDocument] = []
    for href in hrefs:
        url = f"https://pk.mpei.ru{href}" if href.startswith("/") else href
        doc = await fetch_document(url, client=client)
        documents.append(
            FetchedDocument(
                content=doc.content,
                source_url=url,
                metadata={
                    "group_id": href.rsplit("/", 1)[-1].removesuffix(".html"),
                    "title": titles[href],
                },
            )
        )
    return tuple(documents)


async def fetch_misis(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    index = await fetch_document(MISIS_INDEX, client=client)
    html = index.content.decode("utf-8", errors="replace")
    hrefs = sorted(
        {
            href
            for href in re.findall(r'href="([^"]+)"', html)
            if "list/?id=" in href and "BUDJ" in href and "OKM" in href
        }
    )
    index_html = index.content.decode("utf-8", errors="replace")
    link_texts = {
        link_href: unescape(re.sub(r"<[^>]+>", "", link_text)).strip()
        for link_href, link_text in re.findall(
            r'<a[^>]*href="([^"]*list/\?id=[^"]+)"[^>]*>(.*?)</a>',
            index_html,
            re.S,
        )
    }
    documents: list[FetchedDocument] = []
    for href in hrefs:
        url = urljoin(MISIS_INDEX, href)
        doc = await fetch_document(url, client=client)
        group_id = href.rsplit("id=", 1)[-1]
        title = link_texts.get(href) or group_id
        documents.append(
            FetchedDocument(
                content=doc.content,
                source_url=url,
                metadata={"group_id": group_id, "title": title},
            )
        )
    return tuple(documents)


async def fetch_fa(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    doc = await fetch_document(FA_URL, client=client)
    return (doc,)


async def fetch_stankin(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    index = await fetch_document(STANKIN_INDEX, client=client)
    html = index.content.decode("utf-8", errors="replace")
    options = re.findall(
        r'<option value="([^"]+)"[^>]*>\s*([^<]+?)\s*</option>', html
    )
    directions = [value for value, text in options if re.match(r"^\d{2}\.\d{2}\.\d{2}", value)]
    documents: list[FetchedDocument] = []
    for direction in directions:
        params = (
            "PROPERTY_388=%D0%91%D1%8E%D0%B4%D0%B6%D0%B5%D1%82%D0%BD%D0%B0%D1%8F+"
            "%D0%BE%D1%81%D0%BD%D0%BE%D0%B2%D0%B0&PROPERTY_389=1+-+%D0%9E%D1%87%D0%BD%D0%B0%D1%8F"
            f"&PROPERTY_394={quote(direction)}"
            "&PROPERTY_423=&PROPERTY_402=-&COL_CITIZENSHIP=%D0%93%D1%80%D0%B0%D0%B6%D0%B4%D0%B0%D0%BD%D0%B8%D0%BD+%D0%A0%D0%A4"
            "&PROPERTY_747=-&apply_filter=Y&PROPERTY_584=ready&PROPERTY_710=&PROPERTY_410="
            "&LIST_TYPE=ranked&EDU_LEVEL=bs&PROPERTY_418=%D0%9F%D1%80%D0%B8%D0%B5%D0%BC+%D0%BD%D0%B0+%D0%BE%D0%B1%D1%83%D1%87%D0%B5%D0%BD%D0%B8%D0%B5+%D0%BD%D0%B0+%D0%B1%D0%B0%D0%BA%D0%B0%D0%BB%D0%B0%D0%B2%D1%80%D0%B8%D0%B0%D1%82%2F%D1%81%D0%BF%D0%B5%D1%86%D0%B8%D0%B0%D0%BB%D0%B8%D1%82%D0%B5%D1%82"
            "&PROPERTY_413=%7E%D0%A6%D0%91%D0%9E%D0%9F+%26+%7E%D0%A6%D0%A1%D0%9E%D0%9F"
        )
        url = f"{STANKIN_GRID}?{params}"
        doc = await fetch_document(url, client=client)
        documents.append(
            FetchedDocument(
                content=doc.content,
                source_url=url,
                metadata={
                    "group_id": f"bs-{direction}",
                    "title": direction,
                    "financing": "budget",
                },
            )
        )
    return tuple(documents)


async def fetch_msu(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    from packages.parsers.msu import split_sections

    rating = await fetch_document(MSU_RATING, client=client)
    html = rating.content.decode("utf-8", errors="replace")
    deps = sorted(
        {
            href
            for href in re.findall(r'href="([^"]+)"', html)
            if re.search(r"/rating/dep_\d+$", href)
        }
    )
    documents: list[FetchedDocument] = []
    for dep in deps:
        url = f"https://cpk.msu.ru{dep}"
        doc = await fetch_document(url, client=client)
        page = doc.content.decode("utf-8", errors="replace")
        for section in split_sections(page):
            documents.append(
                FetchedDocument(
                    content=section.html.encode("utf-8", errors="replace"),
                    source_url=f"{url}#{section.anchor_id}",
                    metadata={
                        "section_anchor": section.anchor_id,
                        "section_program": section.program,
                        "section_condition": section.condition,
                        "section_seat": section.seat_count,
                        "faculty_code": dep.removeprefix("/rating/"),
                    },
                )
            )
    return tuple(documents)


async def fetch_rudn(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    index = await fetch_document(RUDN_INDEX, client=client)
    html = index.content.decode("utf-8", errors="replace")
    hrefs = sorted(
        {
            href
            for href in re.findall(r'href="([^"]+)"', html)
            if re.search(r"/competition_list/\d+/$", href)
        }
    )
    documents: list[FetchedDocument] = []
    for href in hrefs[:60]:  # лимит на цикл: крупный вуз
        url = href if href.startswith("http") else f"https://admission.rudn.ru{href}"
        doc = await fetch_document(url, client=client)
        group_id = href.rstrip("/").rsplit("/", 1)[-1]
        documents.append(
            FetchedDocument(
                content=doc.content,
                source_url=url,
                metadata={"group_id": group_id, "title": group_id},
            )
        )
    return tuple(documents)


async def fetch_sechenov(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    index = await fetch_document(SECHENOV_INDEX, client=client)
    html = index.content.decode("utf-8", errors="replace")
    group_ids = sorted(
        {
            int(value)
            for value in re.findall(r'data-[a-z-]*group[a-z-]*="(\d+)"', html)
            if int(value) > 0
        }
    )
    titles: dict[int, str] = {}
    for group_id in group_ids:
        marker = f'data-group-id="{group_id}"'
        position = html.find(marker)
        if position == -1:
            continue
        block = html[position:position + 3000]
        text = unescape(re.sub(r"<[^>]+>", " ", block))
        text = re.sub(r"\s+", " ", text)
        match = re.search(r"\d{2}\.\d{2}\.\d{2}\s+([^К]{3,70}?)\s+Количество", text)
        if match:
            titles[group_id] = match.group(1).strip()
    documents: list[FetchedDocument] = []
    for group_id in group_ids:
        url = (
            f"{SECHENOV_API}?COMPETITIVE_GROUP_ID={group_id}&appPage_{group_id}=1"
            "&lang=ru&ADMISSION_LISTS=Y&CONTRACT_IS_PAID=N&ORIGINAL_DOCUMENT=N"
            "&search=&highest_passing_priority=&highest_primary_priority=&header_consent="
        )
        doc = await fetch_document(url, client=client)
        documents.append(
            FetchedDocument(
                content=doc.content,
                source_url=url,
                metadata={"group_id": str(group_id), "title": titles.get(group_id, str(group_id))},
            )
        )
    return tuple(documents)


GUBKIN_API = "https://transfer.priem.gubkin.ru/abiturients_list/api/api.php"


async def _gubkin(client: httpx.AsyncClient, **params: str) -> FetchedDocument:
    url = f"{GUBKIN_API}?act=search&{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return await fetch_document(url, client=client, content_type="application/json")


async def fetch_gubkin(client: httpx.AsyncClient) -> tuple[FetchedDocument, ...]:
    from packages.parsers.html_tables import map_condition

    form = json.loads((await _gubkin(client, method="getForm")).content)["data"]
    if not form:
        return ()
    faculties = json.loads(
        (await _gubkin(client, method="getFaculties", educationFormId="1")).content
    )["data"]
    bachelor = next(
        (item for item in faculties if "акалавр" in str(item.get("name", ""))),
        None,
    )
    if bachelor is None:
        return ()
    groups = json.loads(
        (await _gubkin(
            client, method="getGroups", educationFormId="1", facultyId=str(bachelor["id"])
        )).content
    )["data"]
    documents: list[FetchedDocument] = []
    semaphore = asyncio.Semaphore(6)

    async def fetch_group(group: dict[str, object]) -> None:
        async with semaphore:
            types = json.loads(
                (
                    await _gubkin(
                        client, method="getEducationTypes", contestGroupId=str(group["id"])
                    )
                ).content
            )["data"]
            # основной конкурс («Основные места в рамках КЦП») — id=1;
            # квоты — отдельными snapshot'ами
            selected = [item for item in types if item.get("id") == 1] or types[:1]
            for item in selected:
                url = (
                    f"{GUBKIN_API}?act=search&method=get"
                    f"&educationTypeId={item['id']}&contestGroupId={group['id']}"
                )
                doc = await fetch_document(url, client=client, content_type="application/json")
                condition = map_condition(str(item.get("name", "")))
                documents.append(
                    FetchedDocument(
                        content=doc.content,
                        source_url=url,
                        content_type="application/json",
                        metadata={
                            "group_id": str(group["id"]),
                            "title": str(group.get("name") or group["id"]),
                            "condition": condition,
                        },
                    )
                )

    await asyncio.gather(*(fetch_group(group) for group in groups))
    return tuple(documents)
