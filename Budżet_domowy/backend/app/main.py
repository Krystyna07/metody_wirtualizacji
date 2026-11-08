import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(
    title="Budżet domowy - backend API",
    description="API zarządzania budżetem domowym z bazą PostgreSQL",
    version="1.0.0"
)

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

@app.get("/")
def read_root():
    return {
        "projekt": "Budżet domowy",
        "status": "API dziala poprawnie",
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
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Błąd połączenia z bazą: {str(e)}")

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

        return {
            "status": "success",
            "db_views_counter": views,
            "currency": "PLN",
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "balance": round(total_income - total_expenses, 2),
            "sample_categories": sample_categories
        }
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
    conn.commit()
    cur.close()
    conn.close()
    return new_row

@app.put("/api/transactions/{transaction_id}")
def update_transaction(transaction_id: int, payload: TransactionUpdate):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT * FROM transactions WHERE id = %s;", (transaction_id,))
    existing = cur.fetchone()
    if not existing:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail=f"Transakcja o ID {transaction_id} nie istnieje")

    new_title = payload.title.strip() if payload.title is not None else existing["title"]
    new_amount = payload.amount if payload.amount is not None else float(existing["amount"])
    new_category_id = payload.category_id if payload.category_id is not None else existing["category_id"]

    if not new_title:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Tytuł transakcji nie może być pusty")
    if new_amount <= 0:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Kwota transakcji musi być większa od 0")

    cur.execute("SELECT id FROM categories WHERE id = %s;", (new_category_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Kategoria o ID {new_category_id} nie istnieje")

    cur.execute("""
        UPDATE transactions
        SET title = %s, amount = %s, category_id = %s
        WHERE id = %s
        RETURNING id, title, float8(amount) AS amount, category_id, created_at;
    """, (new_title, new_amount, new_category_id, transaction_id))
    updated = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return updated

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
    return {"status": "deleted", "id": transaction_id}