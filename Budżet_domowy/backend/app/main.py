import os
from fastapi import FastAPI, HTTPException
import redis

app = FastAPI(
    title="Budzet domowy - backend API",
    description = "API zarzadzania budzetem domowym z baza Redis",
    version = "1.0.0"
)

REDIS_HOST = os.getenv("REDIS HOST", "database")
REDIS_PORT = int(os.getenv("REDIS PORT", 6379))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

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
        if r.ping():
            return {"status": "healthy", "database": "connected"}
        else:
            raise HTTPException(status_code=503, detail="Baza danych nie odpowiada")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Błąd połączenia z bazą: {str(e)}")

@app.get("/api/budget/summary")
def get_budget_summary():
    try:
        views = r.incr("budget:summary_views")

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