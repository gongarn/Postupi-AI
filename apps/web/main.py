from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from packages.aggregates import (
    DATA_FILE,
    GroupAggregate,
    groups_by_university,
    load_groups,
    search_groups,
)

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

app = FastAPI(title="Postupi AI — витрина данных", version="0.2.0")

_groups_cache: list[GroupAggregate] | None = None


def _groups() -> list[GroupAggregate]:
    global _groups_cache
    if _groups_cache is None:
        _groups_cache = load_groups()
    return _groups_cache


def _by_id() -> dict[str, GroupAggregate]:
    return {group.id: group for group in _groups()}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, q: str = "") -> HTMLResponse:
    groups = search_groups(_groups(), q)
    by_university = groups_by_university(groups)
    universities = sorted(by_university.items(), key=lambda item: item[1][0].university_name)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "universities": universities,
            "total_groups": len(_groups()),
            "shown_groups": len(groups),
            "query": q,
        },
    )


@app.get("/vuz/{code}", response_class=HTMLResponse)
async def university(request: Request, code: str) -> HTMLResponse:
    by_university = groups_by_university(_groups())
    groups = by_university.get(code)
    if not groups:
        raise HTTPException(status_code=404, detail="university not found")
    return templates.TemplateResponse(
        request,
        "university.html",
        {"code": code, "name": groups[0].university_name, "groups": groups},
    )


@app.get("/napravlenie/{group_id}", response_class=HTMLResponse)
async def napravlenie(request: Request, group_id: str) -> HTMLResponse:
    group = _by_id().get(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="group not found")
    return templates.TemplateResponse(
        request,
        "napravlenie.html",
        {"group": group},
    )


@app.get("/data", response_class=HTMLResponse)
async def data_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "data.html", {})


@app.get("/data/aggregates_2026.csv")
async def aggregates_csv() -> FileResponse:
    if not DATA_FILE.is_file():
        raise HTTPException(status_code=404, detail="aggregates not available")
    return FileResponse(DATA_FILE, media_type="text/csv", filename=DATA_FILE.name)


app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")
