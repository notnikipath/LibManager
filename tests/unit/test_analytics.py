from datetime import UTC, datetime, timedelta

from shared.libmanager_common import (
    calculate_overdue_fine,
    demand_score,
    estimate_search_latency_ms,
    forecast_demand,
    recommend_materials,
)


def test_overdue_fine() -> None:
    due = datetime.now(UTC) - timedelta(days=3)
    fine = calculate_overdue_fine(due, datetime.now(UTC), daily_rate=10)
    assert fine >= 20


def test_demand_and_forecast() -> None:
    assert demand_score(10, 4, 20) > 0
    forecast = forecast_demand([1, 2, 3, 3, 4, 4, 5, 6, 7])
    assert forecast >= 0


def test_recommendations_and_latency() -> None:
    history_tags = ["python", "data", "python"]
    tag_index = {"python": ["MAT-EBOOK-001", "MAT-PRINT-002"], "data": ["MAT-EBOOK-001"]}
    recs = recommend_materials(history_tags, tag_index, limit=3)
    assert recs
    assert estimate_search_latency_ms(catalog_size=1_000_000, cache_hit_ratio=0.9) > 0

