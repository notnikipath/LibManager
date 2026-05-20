# LibManager

LibManager is a microservice platform for library automation:
- catalog and classification (UDC/BBK)
- patrons and e-cards
- checkout/return/renewal with fines
- reservations and notifications
- DRM-enabled ebook access
- visit, demand and inventory reporting

## Services

- `api-gateway` - orchestration and unified workflows
- `catalog-service` - catalog CRUD, classification, search, inventory
- `patron-service` - registration, e-cards, history, debt profile
- `circulation-service` - loans, returns, renewals, debt calculation
- `reservation-service` - queue-based reservations
- `ebooks-service` - upload, DRM token grants, online reading preview
- `reports-service` - visits, demand analytics, inventory snapshots, KPI targets
- `notification-service` - notification delivery history
- `frontend` - React dashboard
- `mobile-app-reader` - React Native app scaffold

## Required stack

- Backend: FastAPI
- DB: PostgreSQL
- Cache: Redis
- File storage: MinIO
- Frontend: React + React Native scaffold

## Run locally

```bash
cd 'your/project/folder'
docker compose up --build -d
```

## Useful URLs

- Gateway: `http://localhost:8600`
- Gateway docs: `http://localhost:8600/docs`
- Frontend: `http://localhost:5186`
- MinIO console: `http://localhost:9001`

## Validation

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Demo workflow

```bash
python scripts/demo_workflow.py
```

## Quality metrics (targets)

- Search time: `< 1 sec`
- Checkout time: `< 10 sec`
- Catalog capacity: `1,000,000 titles`

Gateway writes search and checkout timings to `reports-service` metrics API.
