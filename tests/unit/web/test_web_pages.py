from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.web.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_index_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Postupi" in response.text


def test_university_page_known(client: TestClient) -> None:
    response = client.get("/vuz/itmo")
    assert response.status_code == 200
    assert "ИТМО" in response.text


def test_university_page_unknown(client: TestClient) -> None:
    response = client.get("/vuz/no-such-university")
    assert response.status_code == 404


def test_data_page(client: TestClient) -> None:
    response = client.get("/data")
    assert response.status_code == 200
    assert "aggregates_2026.csv" in response.text


def test_search_filters_groups(client: TestClient) -> None:
    response = client.get("/", params={"q": "программная инженерия"})
    assert response.status_code == 200
    assert "Найдено групп" in response.text


def test_search_empty_result(client: TestClient) -> None:
    response = client.get("/", params={"q": "zzzz-не-существует"})
    assert response.status_code == 200
    assert "Ничего не найдено" in response.text


def test_napravlenie_page(client: TestClient) -> None:
    from packages.aggregates import load_groups

    group = load_groups()[0]
    response = client.get(f"/napravlenie/{group.id}")
    assert response.status_code == 200
    assert group.group_title[:20] in response.text


def test_napravlenie_unknown(client: TestClient) -> None:
    response = client.get("/napravlenie/deadbeef0000")
    assert response.status_code == 404
