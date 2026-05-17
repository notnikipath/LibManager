# Deployment Notes

## Local Docker deployment

```bash
docker compose up --build -d
```

## Services and ports

- Gateway: `8600`
- Catalog: `8601`
- Patron: `8602`
- Circulation: `8603`
- Reservation: `8604`
- Ebooks: `8605`
- Reports: `8606`
- Notification: `8607`
- Frontend: `5186`
- PostgreSQL: `55445`
- Redis: `6390`
- MinIO API: `9000`
- MinIO Console: `9001`

## Environment

Values are provided in `.env.example` and duplicated to `.env` for local start.

## Health checks

- Gateway: `GET /health`
- Aggregated service checks: `GET /services/health`

## Test pipeline

- `python -m ruff check .`
- `python -m pytest -q`
- `docker compose config`
