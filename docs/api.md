# API Overview

## Gateway

- `POST /auth/token`
- `POST /auth/verify`
- `GET /services/health`
- `GET /catalog/search`
- `POST /workflow/checkout-book`
- `POST /workflow/return-book`
- `POST /workflow/reserve-book`
- `POST /workflow/renew-loan`
- `POST /workflow/ebook-read`
- `GET /dashboard/patron/{patron_id}`

## Catalog service

- `GET /materials`
- `GET /materials/{material_id}`
- `POST /materials`
- `PUT /materials/{material_id}`
- `POST /materials/{material_id}/availability`
- `POST /materials/{material_id}/metadata`
- `GET /materials/tag-index`
- `POST /materials/index/rebuild`
- `GET /materials/index/status`
- `GET /inventory/summary`

## Patron service

- `GET /patrons`
- `POST /patrons/register`
- `GET /patrons/{patron_id}`
- `GET /patrons/{patron_id}/history`
- `POST /patrons/{patron_id}/history`
- `GET /patrons/{patron_id}/debts`
- `POST /patrons/{patron_id}/debts/update`
- `POST /patrons/{patron_id}/recommendations`

## Circulation service

- `POST /loans/checkout`
- `GET /loans/{loan_id}`
- `GET /loans/by-patron/{patron_id}`
- `POST /loans/{loan_id}/renew`
- `POST /loans/{loan_id}/return`
- `GET /debts/{patron_id}`
- `POST /debts/{patron_id}/settle`

## Reservation service

- `POST /reservations`
- `GET /reservations`
- `GET /reservations/material/{material_id}/queue`
- `POST /reservations/{reservation_id}/ready`
- `POST /reservations/{reservation_id}/fulfill`
- `POST /reservations/{reservation_id}/cancel`

## Ebooks service

- `POST /ebooks/upload`
- `GET /ebooks`
- `GET /ebooks/{asset_id}`
- `POST /ebooks/grant-access`
- `POST /ebooks/read`

## Reports service

- `POST /reports/visits`
- `GET /reports/visits/stats`
- `POST /reports/demand`
- `GET /reports/demand/top`
- `GET /reports/demand/forecast`
- `POST /reports/inventory/snapshot`
- `GET /reports/inventory/latest`
- `POST /reports/metrics`
- `GET /reports/metrics/targets`
- `GET /reports/export`

## Notification service

- `POST /notify/send`
- `POST /notify/checkout`
- `POST /notify/reservation-ready`
- `GET /notify/history`
