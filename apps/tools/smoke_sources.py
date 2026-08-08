from __future__ import annotations

import asyncio
import sys

import httpx

# Ключевые URL источников: (код вуза, URL, минимальный размер ответа)
SOURCES: tuple[tuple[str, str, int], ...] = (
    ("itmo", "https://abitlk.itmo.ru/api/v1/rating/directions?degree=bachelor", 1000),
    ("hse", "https://pk.hse.ru/admissions/api/competitve-group", 10000),
    ("mipt", "https://pk.mipt.ru/", 1000),
    ("rnimu", "https://ratings.rsmu.ru/data/root.json", 50),
    ("mpei", "https://pk.mpei.ru/inform/list", 10000),
    (
        "misis",
        "https://misis.ru/applicants/admission/progress/baccalaureate-and-specialties/list-of-applicants/",
        10000,
    ),
    (
        "fa",
        "https://www.fa.ru/spiski/listabit.php?id_filial=0&type_list=%D0%B1%D0%BA%D0%BB",
        10000,
    ),
    ("stankin", "https://priem.stankin.ru/bakalavriatispetsialitet/ranked-lists/", 10000),
    ("msu", "https://cpk.msu.ru/rating", 10000),
    ("rudn", "https://admission.rudn.ru/undergraduate/competition_list/", 10000),
    ("sechenov", "https://priem.sechenov.ru/admission-lists/", 10000),
    (
        "gubkin",
        "https://transfer.priem.gubkin.ru/abiturients_list/api/api.php?act=search&method=getForm",
        10,
    ),
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}


async def smoke() -> int:
    failures: list[str] = []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
        for code, url, min_size in SOURCES:
            try:
                response = await client.get(url, headers=HEADERS)
                ok = response.status_code == 200 and len(response.content) >= min_size
                status = "ok" if ok else (
                    f"status={response.status_code} size={len(response.content)}"
                )
                print(f"{code:10s} {status}")
                if not ok:
                    failures.append(code)
            except Exception as exc:  # noqa: BLE001
                print(f"{code:10s} error: {type(exc).__name__}: {str(exc)[:80]}")
                failures.append(code)
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print("ALL SOURCES OK")
    return 0


def main() -> None:
    code = asyncio.run(smoke())
    sys.exit(code)


if __name__ == "__main__":
    main()
