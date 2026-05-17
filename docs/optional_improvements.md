# Optional Improvements

Implemented optional improvements from multiple groups:

1. Group A.1 - Book recommendations:
   - `patron-service` computes recommendations from borrowing history tags.
2. Group A.3 - Demand forecasting:
   - `reports-service` endpoint `GET /reports/demand/forecast`.
3. Group C.1 - Catalog caching:
   - `catalog-service` uses TTL cache for search requests.
4. Group C.2 - Parallel report export:
   - `reports-service` endpoint `GET /reports/export` uses `asyncio.gather`.
5. Group C.4 - Async index refresh:
   - `catalog-service` index rebuild endpoint with background task.
6. Group D.1 - Mobile reader scaffold:
   - `mobile-app-reader` folder with Expo React Native app bootstrap.
