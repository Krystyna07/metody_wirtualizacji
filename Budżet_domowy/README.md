Aplikacja do zarządzania budżetem domowym składająca się z 3 kontenerów:
- **database**: PostgreSQL 15 (`postgres:15-alpine`) z trwałym wolumenem `postgres_data` i skryptem inicjalizującym `db/init.sql` (dwie powiązane tabele: `categories` oraz `transactions`). Brak opublikowanego portu na hoście.
- **backend**: FastAPI (`http://localhost:8000`) z endpointem `/health` i pełnym API CRUD.
- **frontend**: FastAPI + Jinja2 (`http://localhost:3000`) z dwoma widokami (`/` oraz `/transactions`).

## Uruchomienie projektu

Aby uruchomić projekt od czystego stanu (wraz z inicjalizacją bazy danych):
```bash
docker compose down -v
docker compose up --build -d
docker compose ps



1. Cache lub prosta kolejka (np. Redis / RabbitMQ):
    docker exec -it budget_redis redis-cli
    KEYS *
    GET budget_summary_cache


2. Druga usługa asynchroniczna (np. Kafka / ZeroMQ) - frontend wysyła do kolejki zapytanie (od razu widzi odpowiedz); worker w "wolnej chwili" zajmuje się obsługą zapytania; ew. odpytywanie o status zapytania
    docker compose logs -f worker


3. Prometheus + Grafana: `/metrics` na backendzie, scrape, dashboard z min. 2 panelami
    http://localhost:9090
    http_requests_total

    http://localhost:3001
        http://prometheus:9090
        http_requests_total


4. Alerty / detekcja anomalii: strumień zdarzeń → prosta reguła progowa →  zapis alertów (naturalnie daje 2. tabelę) → widok alertów / panel Grafana
    transakcja > 1000
    http://localhost:8000/api/alerts