from __future__ import annotations

import json
import urllib.request

BASE = "http://localhost:8600"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    checkout = request(
        "POST",
        "/workflow/checkout-book",
        {
            "patron_id": "PAT-001",
            "material_id": "MAT-PRINT-001",
            "loan_days": 14,
            "actor_id": "LIB-001",
            "actor_role": "librarian",
        },
    )
    print("Checkout result:")
    print(json.dumps(checkout, ensure_ascii=False, indent=2))

    dashboard = request("GET", "/dashboard/patron/PAT-001")
    print("\nPatron dashboard:")
    print(json.dumps(dashboard, ensure_ascii=False, indent=2))
