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



5. Skalowanie: bezstanowy backend, `--scale`, reverse proxy (nginx) rozdzielający ruch, test obciążeniowy + dowód w logach/Grafanie

docker compose up -d --scale backend=3
docker compose ps
docker compose restart frontend
1..15 | ForEach-Object { curl.exe --no-keepalive -s -o NUL -w "Req $_ -> %{http_code}\n" "http://localhost:8080/api/alerts" }
docker compose logs backend
backend-1  | [75bf1f6e2b60] GET /api/alerts
backend-1  | INFO:     172.19.0.8:54232 - "GET /api/alerts HTTP/1.1" 200 OK
backend-1  | [75bf1f6e2b60] GET /api/alerts
backend-1  | INFO:     172.19.0.8:54248 - "GET /api/alerts HTTP/1.1" 200 OK
backend-1  | [75bf1f6e2b60] GET /api/alerts
backend-1  | INFO:     172.19.0.8:54262 - "GET /api/alerts HTTP/1.1" 200 OK
backend-1  | [75bf1f6e2b60] GET /api/alerts
backend-1  | INFO:     172.19.0.8:54278 - "GET /api/alerts HTTP/1.1" 200 OK
backend-1  | [75bf1f6e2b60] GET /api/alerts


backend-2  | INFO:     172.19.0.8:50386 - "GET /api/alerts HTTP/1.1" 200 OK
backend-2  | [bf1763c282c6] GET /api/alerts
backend-2  | INFO:     172.19.0.8:50396 - "GET /api/alerts HTTP/1.1" 200 OK
backend-2  | [bf1763c282c6] GET /api/alerts
backend-2  | INFO:     172.19.0.8:50400 - "GET /api/alerts HTTP/1.1" 200 OK


backend-3  | INFO:     172.19.0.8:38214 - "GET /api/alerts HTTP/1.1" 200 OK
backend-3  | [48a2311cb80b] GET /api/alerts
backend-3  | INFO:     172.19.0.8:38216 - "GET /api/alerts HTTP/1.1" 200 OK
backend-3  | [48a2311cb80b] GET /api/alerts
backend-3  | INFO:     172.19.0.8:38222 - "GET /api/alerts HTTP/1.1" 200 OK
backend-3  | [48a2311cb80b] GET /api/alerts
backend-3  | INFO:     172.19.0.8:38228 - "GET /api/alerts HTTP/1.1" 200 OK
backend-3  | [48a2311cb80b] GET /api/alerts




6. Implementacja projektu w kubernetes.

kind get clusters
kubectl get pods,svc

$clusters = kind get clusters
docker ps -a --filter "name=kind"


docker ps -a
docker start <? - docker ps -a>
kubectl wait --for=condition=Ready pods --all --timeout=120s

kind create cluster
kubectl apply -f .\k8s\
kubectl wait --for=condition=Ready pods --all --timeout=120s


kubectl port-forward svc/budget-nginx 18080:8080

kubectl get pods,svc
curl.exe -s http://localhost:18080/health
1..6 | ForEach-Object { $r = curl.exe -s -i http://localhost:18080/health; ($r -split "`r?`n" | Where-Object { $_ -match "^HTTP/|x-backend-instance:|^\{" }) -join " | " }


kind get clusters
docker ps -a --filter "name=kind"

docker start kind-control-plane
kubectl wait --for=condition=Ready pods --all --timeout=120s

kubectl port-forward svc/budget-nginx 18080:8080

git log -n 2 --oneline
Get-ChildItem .\k8s


kubectl get pods,svc



curl.exe -s http://localhost:8080/health
1..6 | ForEach-Object { $r = curl.exe -s -i http://localhost:8080/health; ($r -split "`r?`n" | Where-Object { $_ -match "^HTTP/|x-backend-instance:|^\{" }) -join " | " }

kubectl logs -l app=budget-nginx --tail=8

..........................................................................

where.exe kind
where.exe kubectl
Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "kind|kubectl" }

winget install Kubernetes.kind
winget install Kubernetes.kubectl


$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
kind version


kind create cluster
kind load docker-image budet_domowy-backend:latest budet_domowy-frontend:latest budet_domowy-worker:latest postgres:15-alpine redis:7-alpine nginx:alpine
kubectl apply -f .\k8s\
kubectl wait --for=condition=Ready pods --all --timeout=120s


kind load docker-image budet_domowy-backend:latest
kind load docker-image budet_domowy-frontend:latest
kind load docker-image budet_domowy-worker:latest

docker save budet_domowy-backend:latest budet_domowy-frontend:latest budet_domowy-worker:latest -o images.tar
docker exec -i kind-control-plane ctr --namespace=k8s.io images import - < images.tar
Remove-Item images.tar


kubectl wait --for=condition=Ready pods --all --timeout=120s
kubectl get pods,svc


kubectl port-forward svc/budget-nginx 18080:8080


curl.exe -s http://localhost:18080/health



kubectl wait --for=condition=Ready pods --all --timeout=120s
kubectl get pods,svc


kubectl port-forward svc/budget-nginx 18080:8080


curl.exe -s http://localhost:8080/health
1..6 | ForEach-Object { $r = curl.exe -s -i http://localhost:8080/health; ($r -split "`r?`n" | Where-Object { $_ -match "^HTTP/|x-backend-instance:|^\{" }) -join " | " }



Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing | Select-Object StatusCode, StatusDescription


kubectl get pods -l app=budget-frontend
kubectl logs deploy/budget-frontend --tail=20




..........................................................................
Wykorzystanie i przepływ danych w formacie JSON w projekcie „Budżet domowy”

W architekturze aplikacji JSON pełni rolę głównego formatu wymiany danych pomiędzy warstwą prezentacji (frontendem) a warstwą logiki biznesowej (backendem REST API) oraz jest wykorzystywany do serializacji danych w pamięci podręcznej Redis.

1. Przepływ danych pomiędzy przeglądarką, frontendem a backendemWarstwa przeglądarki (HTML + Jinja2):

 Użytkownik nie komunikuje się bezpośrednio z API za pomocą żądań asynchronicznych (AJAX/fetch). Szablony HTML (index.html, categories.html, edit_transaction.html, history.html, alerts.html) są renderowane po stronie serwera frontendu przy użyciu silnika szablonów Jinja2, a operacje modyfikacji danych są wysyłane klasycznymi formularzami HTML (application/x-www-form-urlencoded).Warstwa frontendu (FastAPI + requests): Aplikacja frontendowa odbiera dane z formularzy (urllib.parse.parse_qs), konwertuje je do odpowiednich typów (str, float, int) i przesyła do backendu (BACKEND_URL) w formacie JSON za pomocą biblioteki requests:requests.post(..., json=payload) oraz requests.put(..., json=payload) automatycznie serializują słownik Pythona do formatu JSON i ustawiają nagłówek Content-Type: application/json.Odpowiedzi z backendu są deserializowane metodą resp.json() do struktur słownikowych/listowych i przekazywane do szablonów HTML.



2. Struktura komunikatów JSON w REST API (Backend FastAPI)Dane wejściowe (POST, PUT, PATCH dla /api/transactions):

Walidacja i parsowanie przychodzącego JSON-a realizowane są przez modele Pydantic (TransactionCreate, TransactionPut, TransactionPatch), zawierające pola: title (str), amount (float), category_id (int) oraz opcjonalne changed_by (Optional[str]). W przypadku metody PATCH wszystkie pola są opcjonalne, co umożliwia częściową aktualizację zasobu.Dane wyjściowe (GET oraz odpowiedzi po zapisie/edycji):Endpoint GET /api/budget/summary zwraca zagregowany obiekt JSON zawierający m.in. status, db_views_counter, currency, total_income, total_expenses, balance oraz tablicę obiektów sample_categories.Endpointy GET /api/categories, GET /api/transactions, GET /api/transactions/archived, GET /api/transactions/{id}/history oraz GET /api/alerts zwracają tablice obiektów JSON powstałe z wyników zapytań SQL (RealDictCursor w psycopg2), z jawnym rzutowaniem wartości liczbowych na typy float i int.



3. Walidacja i obsługa błędów w formacie JSON

W przypadku przesłania niepoprawnej struktury lub błędnych typów danych w ciele żądania JSON, niestandardowy handler wyjątku RequestValidationError zwraca odpowiedź JSONResponse ze statusem HTTP 400 oraz ustandaryzowaną strukturą:{"detail": "Błędne dane wejściowe (walidacja JSON nie powiodła się)", "errors": [...]}.Błędy logiki biznesowej (np. pusta nazwa transakcji, kwota $\le 0$, brak kategorii lub rekordu o podanym ID) zwracane są jako obiekty JSON poprzez HTTPException (400, 404, 500, 503), a frontend odczytuje pole detail z odpowiedzi JSON (resp.json().get("detail")) i prezentuje komunikat użytkownikowi.


4. Serializacja JSON w pamięci podręcznej Redis i rola NginxRedis (budget_summary_cache): 

W endpoincie GET /api/budget/summary wynikowy słownik podsumowania jest serializowany do ciągu znaków JSON za pomocą json.dumps(result) i zapisywany w Redisie na 30 sekund (r.setex). Przy kolejnych odczytach w oknie TTL dane są odtwarzane poprzez json.loads(cached_summary) bez obciążania bazy PostgreSQL. Każda modyfikacja transakcji (POST, PUT, PATCH, DELETE) unieważnia klucz w pamięci podręcznej (r.delete("budget_summary_cache")).Nginx (Reverse Proxy): Serwer Nginx przekazuje żądania HTTP oraz nagłówki sieciowe (Host, X-Real-IP, X-Forwarded-For, X-Forwarded-Proto) do usług wewnętrznych bez ingerencji w treść przesyłanych ładunków JSON.