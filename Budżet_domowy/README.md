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