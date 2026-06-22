from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

import app as app_module


def ddg_html(*profiles: tuple[str, str, str, str]) -> str:
    cards = []
    for slug, name, title, company in profiles:
        cards.append(
            f"""
            <div class="result">
              <a class="result__a" href="https://www.linkedin.com/in/{slug}">
                {name} - {title} at {company} | LinkedIn
              </a>
              <a class="result__snippet">{title} at {company}</a>
            </div>
            """
        )
    return "<html><body>" + "".join(cards) + "</body></html>"


@pytest.fixture(autouse=True)
def clear_search_cache() -> None:
    app_module.SEARCH_CACHE.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app_module.app)


def mock_search(monkeypatch: pytest.MonkeyPatch, result: str | Exception | Callable[[str], str]) -> None:
    def fake_search(query: str) -> str:
        if isinstance(result, Exception):
            raise result
        return result(query) if callable(result) else result

    monkeypatch.setattr(app_module.ddg_client, "search", fake_search)


def search_headers(identity: str) -> dict[str, str]:
    return {
        "x-forwarded-for": f"198.51.100.{identity}",
        "cookie": f"uid=test-{identity}",
    }


def test_nestle_procurement_returns_ranked_profiles(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_search(
        monkeypatch,
        ddg_html(
            ("an-nguyen", "An Nguyen", "Procurement Manager", "Nestle Vietnam"),
            ("binh-tran", "Binh Tran", "Senior Buyer", "Nestle Vietnam"),
            ("chi-le", "Chi Le", "Purchasing Specialist", "Nestle Vietnam"),
        ),
    )

    response = client.post(
        "/api/search",
        json={"company": "Nestle Vietnam", "mst": None, "role": "procurement"},
        headers=search_headers("11"),
    )

    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert len(profiles) >= 2
    assert all("nestle" in profile["company"].lower() for profile in profiles)
    assert profiles == sorted(profiles, key=lambda item: item["score"], reverse=True)


def test_vietnamese_company_fans_out_without_accents(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    queries: list[str] = []

    def response_for_query(query: str) -> str:
        queries.append(query)
        if "Trung Nguyen" in query:
            return ddg_html(
                ("dung-vo", "Dung Vo", "Procurement Manager", "Công ty CP Cà Phê Trung Nguyên"),
            )
        return "<html><body></body></html>"

    mock_search(monkeypatch, response_for_query)
    response = client.post(
        "/api/search",
        json={"company": "Công ty CP Cà Phê Trung Nguyên", "mst": None, "role": "procurement"},
        headers=search_headers("12"),
    )

    assert response.status_code == 200
    assert len(queries) == 2
    assert "Trung Nguyen" in queries[1]
    assert len(response.json()["profiles"]) >= 1


def test_valid_mst_builds_masothue_link(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_search(monkeypatch, app_module.ddg_client.DDGEmpty("empty"))
    response = client.post(
        "/api/search",
        json={"company": "Cong ty ABC", "mst": "0301234567", "role": "sales"},
        headers=search_headers("13"),
    )

    assert response.status_code == 200
    assert response.json()["links"]["masothue"] == "https://masothue.com/0301234567-cong-ty-abc"


def test_empty_mst_uses_google_fallback(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_search(monkeypatch, app_module.ddg_client.DDGEmpty("empty"))
    response = client.post(
        "/api/search",
        json={"company": "Cong ty ABC", "mst": None, "role": "sales"},
        headers=search_headers("14"),
    )

    assert response.status_code == 200
    assert response.json()["links"]["masothue"].startswith("https://www.google.com/search?q=")


def test_unknown_company_returns_empty_warning(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_search(monkeypatch, app_module.ddg_client.DDGEmpty("empty"))
    response = client.post(
        "/api/search",
        json={"company": "Cong ty Khong Ton Tai XYZ", "mst": None, "role": "logistics"},
        headers=search_headers("15"),
    )

    assert response.status_code == 200
    assert response.json()["profiles"] == []
    assert "Không tìm thấy" in response.json()["warnings"][0]


def test_eleventh_request_from_same_identity_is_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_search(monkeypatch, app_module.ddg_client.DDGEmpty("empty"))
    responses = []
    for index in range(11):
        responses.append(
            client.post(
                "/api/search",
                json={"company": f"Rate Test {index}", "mst": None, "role": "sales"},
                headers=search_headers("16"),
            )
        )

    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[10].status_code == 429
    assert "Hết lượt" in responses[10].json()["error"]


def test_ddg_captcha_returns_vietnamese_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    mock_search(monkeypatch, app_module.ddg_client.DDGBlocked("captcha"))
    response = client.post(
        "/api/search",
        json={"company": "Blocked Test", "mst": None, "role": "procurement"},
        headers=search_headers("17"),
    )

    assert response.status_code == 503
    assert response.json() == {"error": "Hệ thống tạm nghỉ, thử lại sau 1 phút"}
