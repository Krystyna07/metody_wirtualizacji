import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(
    title="Budżet domowy - backend API",
    description="API z obsługą bazy danych, historii zmian (KM3), Redis, Prometheus i Alertów",
    version="3.0.0"
)

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint'])
INSTANCE_ID = os.getenv("HOSTNAME", "unknown")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": "Błędne dane wejściowe (walidacja JSON nie powiodła się)", "errors": exc.errors()},
    )


DB_HOST = os.getenv("DB_HOST", "database")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "budget_db")
DB_USER = os.getenv("DB_USER", "postgres_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres_password")


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


class TransactionCreate(BaseModel):
    title: str
    amount: float
    category_id: int
    changed_by: Optional[str] = None


class TransactionPut(BaseModel):
    title: str
    amount: float
    category_id: int
    changed_by: Optional[str] = None


class TransactionPatch(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    category_id: Optional[int] = None
    changed_by: Optional[str] = None


def resolve_actor(body_actor: Optional[str], header_actor: Optional[str]) -> str:
    if body_actor and body_actor.strip():
        return body_actor.strip()
    if header_actor and header_actor.strip():
        return header_actor.strip()
    return "Użytkownik"


def record_history(cur, transaction_id: int, action: str, changed_by: str, details: str):
    cur.execute(
        """
        INSERT INTO transaction_history (transaction_id, action, changed_by, details)
        VALUES (%s, %s, %s, %s);
        """,
        (transaction_id, action, changed_by, details)
    )


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    print(f"[{INSTANCE_ID}] {request.method} {request.url.path}", flush=True)
    response = await call_next(request)
    response.headers["X-Backend-Instance"] = INSTANCE_ID
    return response


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
def read_root():
    return {
        "projekt": "Budżet domowy",
        "status": "API działa poprawnie (KM3 - historia zmian aktywna)",
        "docs_url": "/docs"
    }


@app.get("/health")
def healthcheck():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        r.ping()
        return {"status": "healthy", "database": "connected", "redis": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Błąd połączenia z usługami: {str(e)}")


@app.get("/api/categories")
def get_categories():
    default_limits = {
        "Mieszkanie": 2000.00,
        "Jedzenie": 1000.00,
        "Rozrywka": 300.00,
        "Wynagrodzenie": 5000.00
    }
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT c.id, c.name, c.type, COALESCE(SUM(t.amount), 0) AS spent
        FROM categories c
        LEFT JOIN transactions t ON c.id = t.category_id AND t.is_deleted = FALSE
        GROUP BY c.id, c.name, c.type
        ORDER BY c.id;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "name": row["name"],
            "type": row["type"],
            "limit": default_limits.get(row["name"], 1000.00),
            "spent": float(row["spent"])
        })
    return result


@app.get("/api/budget/summary")
def get_budget_summary():
    cached_summary = r.get("budget_summary_cache")
    if cached_summary:
        return json.loads(cached_summary)

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "INSERT INTO stats (key, val) VALUES ('views', 1) "
            "ON CONFLICT (key) DO UPDATE SET val = stats.val + 1 RETURNING val;"
        )
        views = cur.fetchone()["val"]
        conn.commit()

        cur.execute("""
            SELECT COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE c.type = 'income' AND t.is_deleted = FALSE;
        """)
        total_income = float(cur.fetchone()["total"])

        cur.execute("""
            SELECT COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE c.type = 'expense' AND t.is_deleted = FALSE;
        """)
        total_expenses = float(cur.fetchone()["total"])

        cur.execute("""
            SELECT c.name AS category, COALESCE(SUM(t.amount), 0) AS amount
            FROM categories c
            LEFT JOIN transactions t ON c.id = t.category_id AND t.is_deleted = FALSE
            WHERE c.type = 'expense'
            GROUP BY c.id, c.name
            ORDER BY c.id;
        """)
        sample_categories = [
            {"category": row["category"], "amount": float(row["amount"])}
            for row in cur.fetchall()
        ]

        cur.close()
        conn.close()

        result = {
            "status": "success",
            "db_views_counter": views,
            "currency": "PLN",
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "balance": round(total_income - total_expenses, 2),
            "sample_categories": sample_categories
        }

        r.setex("budget_summary_cache", 30, json.dumps(result))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")


@app.get("/api/transactions")
def get_transactions():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT t.id, t.title, float8(t.amount) AS amount, t.category_id,
               c.name AS category_name, c.type AS category_type, t.created_at
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.is_deleted = FALSE
        ORDER BY t.id DESC;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.get("/api/transactions/archived")
def get_archived_transactions():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT t.id, t.title, float8(t.amount) AS amount, t.category_id,
               c.name AS category_name, c.type AS category_type, t.created_at
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.is_deleted = TRUE
        ORDER BY t.id DESC;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@app.get("/api/transactions/{transaction_id}")
def get_transaction(transaction_id: int):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT t.id, t.title, float8(t.amount) AS amount, t.category_id,
               c.name AS category_name, c.type AS category_type, t.created_at
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.id = %s AND t.is_deleted = FALSE;
    """, (transaction_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Transakcja o ID {transaction_id} nie istnieje")
    return row


@app.post("/api/transactions", status_code=201)
def create_transaction(payload: TransactionCreate, x_user: Optional[str] = Header(default=None)):
    if not payload.title or not payload.title.strip():
        raise HTTPException(status_code=400, detail="Tytuł transakcji nie może być pusty")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Kwota transakcji musi być większa od 0")

    actor = resolve_actor(payload.changed_by, x_user)
    clean_title = payload.title.strip()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id, name FROM categories WHERE id = %s;", (payload.category_id,))
    cat = cur.fetchone()
    if not cat:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Kategoria o ID {payload.category_id} nie istnieje")

    cur.execute("""
        INSERT INTO transactions (title, amount, category_id)
        VALUES (%s, %s, %s)
        RETURNING id, title, float8(amount) AS amount, category_id, created_at;
    """, (clean_title, payload.amount, payload.category_id))
    new_row = cur.fetchone()

    record_history(
        cur,
        new_row["id"],
        "CREATE",
        actor,
        f"Dodano transakcję: '{clean_title}' ({payload.amount:.2f} PLN, kategoria: {cat['name']})"
    )

    if payload.amount > 1000.0:
        cur.execute("""
            INSERT INTO alerts (message, amount) VALUES (%s, %s);
        """, (f"Wykryto wysoką transakcję: {clean_title}", payload.amount))

    conn.commit()
    cur.close()
    conn.close()

    r.delete("budget_summary_cache")
    return new_row


@app.put("/api/transactions/{transaction_id}")
def update_transaction_put(
    transaction_id: int,
    payload: TransactionPut,
    x_user: Optional[str] = Header(default=None)
):
    if not payload.title or not payload.title.strip():
        raise HTTPException(status_code=400, detail="Tytuł transakcji nie może być pusty")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Kwota transakcji musi być większa od 0")

    actor = resolve_actor(payload.changed_by, x_user)
    clean_title = payload.title.strip()

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT id, title, float8(amount) AS amount, category_id FROM transactions WHERE id = %s AND is_deleted = FALSE;",
        (transaction_id,)
    )
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail=f"Transakcja o ID {transaction_id} nie istnieje")

    cur.execute("SELECT id, name FROM categories WHERE id = %s;", (payload.category_id,))
    cat = cur.fetchone()
    if not cat:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Kategoria o ID {payload.category_id} nie istnieje")

    cur.execute("""
        UPDATE transactions
        SET title = %s, amount = %s, category_id = %s
        WHERE id = %s
        RETURNING id, title, float8(amount) AS amount, category_id, created_at;
    """, (clean_title, payload.amount, payload.category_id, transaction_id))
    updated_row = cur.fetchone()

    changes = []
    if existing["title"] != clean_title:
        changes.append(f"tytuł: '{existing['title']}' -> '{clean_title}'")
    if float(existing["amount"]) != float(payload.amount):
        changes.append(f"kwota: {existing['amount']:.2f} -> {payload.amount:.2f} PLN")
    if existing["category_id"] != payload.category_id:
        changes.append(f"kategoria ID: {existing['category_id']} -> {payload.category_id} ({cat['name']})")
    details = "Zaktualizowano rekord (" + (", ".join(changes) if changes else "bez zmiany wartości pól") + ")"

    record_history(cur, transaction_id, "UPDATE", actor, details)

    if payload.amount > 1000.0 and float(existing["amount"]) <= 1000.0:
        cur.execute("""
            INSERT INTO alerts (message, amount) VALUES (%s, %s);
        """, (f"Wykryto wysoką transakcję po edycji: {clean_title}", payload.amount))

    conn.commit()
    cur.close()
    conn.close()

    r.delete("budget_summary_cache")
    return updated_row


@app.patch("/api/transactions/{transaction_id}")
def update_transaction_patch(
    transaction_id: int,
    payload: TransactionPatch,
    x_user: Optional[str] = Header(default=None)
):
    if payload.title is None and payload.amount is None and payload.category_id is None:
        raise HTTPException(status_code=400, detail="Należy podać co najmniej jedno pole do aktualizacji")
    if payload.title is not None and not payload.title.strip():
        raise HTTPException(status_code=400, detail="Tytuł transakcji nie może być pusty")
    if payload.amount is not None and payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Kwota transakcji musi być większa od 0")

    actor = resolve_actor(payload.changed_by, x_user)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        "SELECT id, title, float8(amount) AS amount, category_id FROM transactions WHERE id = %s AND is_deleted = FALSE;",
        (transaction_id,)
    )
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail=f"Transakcja o ID {transaction_id} nie istnieje")

    new_title = payload.title.strip() if payload.title is not None else existing["title"]
    new_amount = payload.amount if payload.amount is not None else float(existing["amount"])
    new_category_id = payload.category_id if payload.category_id is not None else existing["category_id"]

    cur.execute("SELECT id, name FROM categories WHERE id = %s;", (new_category_id,))
    cat = cur.fetchone()
    if not cat:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Kategoria o ID {new_category_id} nie istnieje")

    cur.execute("""
        UPDATE transactions
        SET title = %s, amount = %s, category_id = %s
        WHERE id = %s
        RETURNING id, title, float8(amount) AS amount, category_id, created_at;
    """, (new_title, new_amount, new_category_id, transaction_id))
    updated_row = cur.fetchone()

    changes = []
    if existing["title"] != new_title:
        changes.append(f"tytuł: '{existing['title']}' -> '{new_title}'")
    if float(existing["amount"]) != float(new_amount):
        changes.append(f"kwota: {existing['amount']:.2f} -> {new_amount:.2f} PLN")
    if existing["category_id"] != new_category_id:
        changes.append(f"kategoria ID: {existing['category_id']} -> {new_category_id} ({cat['name']})")
    details = "Częściowa aktualizacja PATCH (" + (", ".join(changes) if changes else "bez zmiany wartości") + ")"

    record_history(cur, transaction_id, "UPDATE", actor, details)

    conn.commit()
    cur.close()
    conn.close()

    r.delete("budget_summary_cache")
    return updated_row


@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, x_user: Optional[str] = Header(default=None)):
    actor = resolve_actor(None, x_user)

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        UPDATE transactions
        SET is_deleted = TRUE
        WHERE id = %s AND is_deleted = FALSE
        RETURNING id, title, float8(amount) AS amount;
        """,
        (transaction_id,)
    )
    deleted = cur.fetchone()

    if not deleted:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail=f"Transakcja o ID {transaction_id} nie istnieje")

    record_history(
        cur,
        transaction_id,
        "DELETE",
        actor,
        f"Usunięto (przeniesiono do archiwum) transakcję: '{deleted['title']}' ({deleted['amount']:.2f} PLN)"
    )

    conn.commit()
    cur.close()
    conn.close()

    r.delete("budget_summary_cache")
    return {"status": "deleted", "id": transaction_id}


@app.get("/api/transactions/{transaction_id}/history")
def get_transaction_history(transaction_id: int):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id, title, is_deleted FROM transactions WHERE id = %s;", (transaction_id,))
    tx = cur.fetchone()
    if not tx:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail=f"Transakcja o ID {transaction_id} nie istnieje")

    cur.execute("""
        SELECT id, transaction_id, action, changed_by, changed_at, details
        FROM transaction_history
        WHERE transaction_id = %s
        ORDER BY changed_at ASC, id ASC;
    """, (transaction_id,))
    history_rows = cur.fetchall()
    cur.close()
    conn.close()

    return history_rows


@app.get("/api/alerts")
def get_alerts():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM alerts ORDER BY id DESC;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows