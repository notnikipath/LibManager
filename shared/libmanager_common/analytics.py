from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime


def calculate_overdue_fine(due_date: datetime, returned_at: datetime | None = None, daily_rate: float = 12.0) -> float:
    end_time = returned_at or datetime.now(UTC)
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=UTC)
    if end_time <= due_date:
        return 0.0
    days_overdue = max((end_time - due_date).days, 0)
    return round(days_overdue * max(daily_rate, 0), 2)


def demand_score(checkouts: int, reservations: int, views: int) -> float:
    score = checkouts * 1.0 + reservations * 0.8 + views * 0.25
    return round(score, 2)


def forecast_demand(last_30_days: list[int]) -> float:
    if not last_30_days:
        return 0.0
    window = last_30_days[-7:] if len(last_30_days) >= 7 else last_30_days
    trend = (window[-1] - window[0]) / max(len(window) - 1, 1)
    return round(max(0.0, (sum(window) / len(window)) + trend * 3), 2)


def recommend_materials(history_tags: list[str], catalog_tag_index: dict[str, list[str]], limit: int = 5) -> list[str]:
    if not history_tags:
        return []
    tag_weights = Counter(history_tags)
    scores: Counter[str] = Counter()
    for tag, weight in tag_weights.items():
        for material_id in catalog_tag_index.get(tag, []):
            scores[material_id] += weight
    return [material_id for material_id, _ in scores.most_common(limit)]


def estimate_search_latency_ms(catalog_size: int, cache_hit_ratio: float) -> float:
    # Approximation: lower with cache hit, grows sub-linearly with catalog size.
    base = 120 + (catalog_size ** 0.42)
    cache_bonus = min(max(cache_hit_ratio, 0.0), 1.0) * 180
    return round(max(80.0, base - cache_bonus), 2)
