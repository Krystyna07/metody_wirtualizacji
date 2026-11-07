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
    return [
        {"name": "Mieszkanie", "limit": 2000.00, "spent": 1600.00},
        {"name": "Jedzenie", "limit": 1000.00, "spent": 500.00},
        {"name": "Rozrywka", "limit": 300.00, "spent": 100.00}
    ]


@app.get("/api/budget/summary")
def get_budget_summary():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, val INT);")
        cur.execute("INSERT INTO stats (key, val) VALUES ('views', 1) ON CONFLICT (key) DO UPDATE SET val = stats.val + 1 RETURNING val;")
        views = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return {
            "status": "success",
            "db_views_counter": views,
            "currancy": "PLN",
            "total_income": 3000.00,
            "total_expenses": 2200.00,
            "balance": 213.70,
            "sample_categories": [
                {"category": "Mieszkanie", "amount": 1600.00},
                {"category": "Jedzenie", "amount": 500.00},
                {"category": "Rozrywka", "amount": 100.00}
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd bazy danych: {str(e)}")