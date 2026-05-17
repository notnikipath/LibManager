# Architecture

## Context

LibManager automates core library operations across physical and digital collection channels. The platform supports catalog management, patron lifecycle, lending, reservations, DRM-protected ebooks, and reporting.

## Service map

- `api-gateway`: entrypoint, service health, auth token endpoints, orchestration workflows
- `catalog-service`: material CRUD, UDC/BBK classification, search, inventory summary, index rebuild
- `patron-service`: registration, e-card generation, borrowing history, debt profile, recommendations
- `circulation-service`: checkout, return, renew, debt calculation
- `reservation-service`: reservation queue, ready and fulfill events
- `ebooks-service`: ebook upload, DRM fingerprinting, access token grant, online read preview
- `reports-service`: visit stats, demand analysis, inventory snapshots, KPI metrics, parallel export
- `notification-service`: checkout and reservation notifications

## Infrastructure

- PostgreSQL for core operational storage
- Redis for cache and lightweight state acceleration
- MinIO for ebook object storage abstraction
- Docker Compose for local orchestration

## Key workflows

1. Checkout flow in gateway:
   - check material availability
   - check patron debt
   - create loan
   - decrement available copies
   - append patron history
   - notify patron
   - write demand and latency metrics
2. Return flow:
   - close loan and calculate fine
   - increment copies
   - synchronize debt profile
3. Reservation flow:
   - queue reservation for shelf item
   - notification when item becomes ready
4. Ebook flow:
   - upload DRM asset
   - grant short-lived access token
   - read online preview with watermark

## Scalability notes

- Catalog search uses in-process TTL caching and index rebuild endpoint.
- Reporting supports parallel section export with `asyncio.gather`.
- Catalog capacity target is aligned to 1M titles.
- Gateway tracks search and checkout timings against SLA targets.
