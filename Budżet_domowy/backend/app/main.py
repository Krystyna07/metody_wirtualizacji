import os
import json
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(
    title="Budżet domowy - backend API",
    description="API z pełną obsługą baz danych, Redis, Prometheus, Workerów i Alertów",
    version="2.0.0"
)

REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP Requests', ['method', 'endpoint'])

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

class TransactionUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    category_id: Optional[int] = None

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path).inc()
    response = await call_next(request)
    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/")
def read_root():
    return {
        "projekt": "Budżet domowy",
        "status": "API dziala poprawnie zbonusami",
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
        LEFT JOIN transactions t ON c.id = t.category_id
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

        cur.execute("INSERT INTO stats (key, val) VALUES ('views', 1) ON CONFLICT (key) DO UPDATE SET val = stats.val + 1 RETURNING val;")
        views = cur.fetchone()["val"]
        conn.commit()

        cur.execute("""
            SELECT COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE c.type = 'income';
        """)
        total_income = float(cur.fetchone()["total"])

        cur.execute("""
            SELECT COALESCE(SUM(t.amount), 0) AS total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE c.type = 'expense';
        """)
        total_expenses = float(cur.fetchone()["total"])

        cur.execute("""
            SELECT c.name AS category, COALESCE(SUM(t.amount), 0) AS amount
            FROM categories c
            LEFT JOIN transactions t ON c.id = t.category_id
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
        WHERE t.id = %s;
    """, (transaction_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Transakcja o ID {transaction_id} nie istnieje")
    return row

@app.post("/api/transactions", status_code=201)
def create_transaction(payload: TransactionCreate):
    if not payload.title or not payload.title.strip():
        raise HTTPException(status_code=400, detail="Tytuł transakcji nie może być pusty")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Kwota transakcji musi być większa od 0")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT id FROM categories WHERE id = %s;", (payload.category_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Kategoria o ID {payload.category_id} nie istnieje")

    cur.execute("""
        INSERT INTO transactions (title, amount, category_id)
        VALUES (%s, %s, %s)
        RETURNING id, title, float8(amount) AS amount, category_id, created_at;
    """, (payload.title.strip(), payload.amount, payload.category_id))
    new_row = cur.fetchone()

    if payload.amount > 1000.0:
        cur.execute("""
            INSERT INTO alerts (message, amount) VALUES (%s, %s);
        """, (f"Wykryto wysoką transakcję: {payload.title}", payload.amount))

    conn.commit()
    cur.close()
    conn.close()

    r.delete("budget_summary_cache")
    return new_row

@app.get("/api/alerts")
def get_alerts():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM alerts ORDER BY id DESC;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.delete("/api/transactions/{transaction_id}")
def delete_transaction(transaction_id: int):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("DELETE FROM transactions WHERE id = %s RETURNING id;", (transaction_id,))
    deleted = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Transakcja o ID {transaction_id} nie istnieje")
    
    r.delete("budget_summary_cache")
    return {"status": "deleted", "id": transaction_id}