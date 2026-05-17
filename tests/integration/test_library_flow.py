from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]

catalog_module = load_module("catalog_module", ROOT / "catalog-service" / "app" / "main.py")
patron_module = load_module("patron_module", ROOT / "patron-service" / "app" / "main.py")
circulation_module = load_module("circulation_module", ROOT / "circulation-service" / "app" / "main.py")
reservation_module = load_module("reservation_module", ROOT / "reservation-service" / "app" / "main.py")
ebooks_module = load_module("ebooks_module", ROOT / "ebooks-service" / "app" / "main.py")
reports_module = load_module("reports_module", ROOT / "reports-service" / "app" / "main.py")
notification_module = load_module("notification_module", ROOT / "notification-service" / "app" / "main.py")

catalog_client = TestClient(catalog_module.app)
patron_client = TestClient(patron_module.app)
circulation_client = TestClient(circulation_module.app)
reservation_client = TestClient(reservation_module.app)
ebooks_client = TestClient(ebooks_module.app)
reports_client = TestClient(reports_module.app)
notification_client = TestClient(notification_module.app)


def test_checkout_and_return_flow() -> None:
    material_resp = catalog_client.get("/materials/MAT-PRINT-001")
    assert material_resp.status_code == 200
    material = material_resp.json()
    initial_available = material["copies_available"]

    debt_resp = circulation_client.get("/debts/PAT-001")
    assert debt_resp.status_code == 200
    assert debt_resp.json()["total_debt_rub"] == 0.0

    loan_resp = circulation_client.post(
        "/loans/checkout",
        json={
            "patron_id": "PAT-001",
            "material_id": material["material_id"],
            "loan_days": 14,
            "actor_id": "LIB-001",
            "actor_role": "librarian",
        },
    )
    assert loan_resp.status_code == 200
    loan = loan_resp.json()

    availability_resp = catalog_client.post(
        f"/materials/{material['material_id']}/availability",
        json={
            "copies_available": initial_available - 1,
            "actor_id": "LIB-001",
            "actor_role": "librarian",
        },
    )
    assert availability_resp.status_code == 200
    assert availability_resp.json()["copies_available"] == initial_available - 1

    history_resp = patron_client.post(
        "/patrons/PAT-001/history",
        json={
            "loan": {
                "loan_id": loan["loan_id"],
                "material_id": material["material_id"],
                "title": material["title"],
                "tags": material["tags"],
                "status": loan["status"],
                "due_date": loan["due_date"],
            },
            "actor_id": "LIB-001",
            "actor_role": "librarian",
        },
    )
    assert history_resp.status_code == 200

    returned_resp = circulation_client.post(
        f"/loans/{loan['loan_id']}/return",
        json={"actor_id": "LIB-001", "actor_role": "librarian"},
    )
    assert returned_resp.status_code == 200

    availability_back = catalog_client.post(
        f"/materials/{material['material_id']}/availability",
        json={
            "copies_available": initial_available,
            "actor_id": "LIB-001",
            "actor_role": "librarian",
        },
    )
    assert availability_back.status_code == 200
    assert availability_back.json()["copies_available"] == initial_available


def test_reservation_ebook_and_reports_flow() -> None:
    reserve_resp = reservation_client.post(
        "/reservations",
        json={
            "patron_id": "PAT-001",
            "material_id": "MAT-PRINT-001",
            "pickup_branch": "Central Library",
            "actor_id": "LIB-001",
            "actor_role": "librarian",
        },
    )
    assert reserve_resp.status_code == 200
    reservation = reserve_resp.json()

    ready_resp = reservation_client.post(
        f"/reservations/{reservation['reservation_id']}/ready",
        json={"actor_id": "LIB-001", "actor_role": "librarian"},
    )
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"

    notification_resp = notification_client.post(
        "/notify/reservation-ready",
        json={
            "patron_id": "PAT-001",
            "material_title": "Clean Architecture",
            "pickup_branch": "Central Library",
            "actor_role": "system",
        },
    )
    assert notification_resp.status_code == 200

    upload_resp = ebooks_client.post(
        "/ebooks/upload",
        json={
            "material_id": "MAT-EBOOK-001",
            "title": "Python for Data Analysis",
            "author": "Wes McKinney",
            "file_name": "python-data-analysis.txt",
            "content_text": "Chapter 1. Intro to data structures and pandas...",
            "drm_watermark": True,
            "actor_id": "LIB-001",
            "actor_role": "librarian",
        },
    )
    assert upload_resp.status_code == 200
    asset = upload_resp.json()

    grant_resp = ebooks_client.post(
        "/ebooks/grant-access",
        json={
            "asset_id": asset["asset_id"],
            "patron_id": "PAT-001",
            "minutes": 60,
            "actor_id": "LIB-001",
            "actor_role": "librarian",
        },
    )
    assert grant_resp.status_code == 200
    token = grant_resp.json()["token"]

    read_resp = ebooks_client.post("/ebooks/read", json={"token": token})
    assert read_resp.status_code == 200
    assert "watermark" in read_resp.json()

    demand_resp = reports_client.post(
        "/reports/demand",
        json={"material_id": "MAT-EBOOK-001", "event_type": "view"},
    )
    assert demand_resp.status_code == 200

    top_resp = reports_client.get("/reports/demand/top")
    assert top_resp.status_code == 200
    assert "items" in top_resp.json()

