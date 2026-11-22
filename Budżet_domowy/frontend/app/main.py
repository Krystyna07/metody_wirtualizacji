import os
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import requests

app = FastAPI(title="Budzet domowy - frontend")
templates = Jinja2Templates(directory="app/templates")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

@app.get("/", response_class=HTMLResponse)
def read_index(request: Request, msg: str = None, err: str = None):
    data = {}
    categories = []
    error = err
    try:
        resp = requests.get(f"{BACKEND_URL}/api/budget/summary", timeout=3)
        c_resp = requests.get(f"{BACKEND_URL}/api/categories", timeout=3)

        if resp.status_code == 200 and c_resp.status_code == 200:
            data = resp.json()
            categories = c_resp.json()
        else:
            error = f"Backend zwrócił błąd ({resp.status_code})"
    except Exception as e:
        error = f"Brak połączenia z backendem: {str(e)}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "budget": data,
            "categories": categories,
            "error": error,
            "msg": msg
        }
    )

@app.get("/kategorie", response_class=HTMLResponse)
def read_categories(request: Request, msg: str = None, err: str = None):
    categories_data = []
    transactions = []
    error = err
    try:
        resp = requests.get(f"{BACKEND_URL}/api/categories", timeout=3)
        t_resp = requests.get(f"{BACKEND_URL}/api/transactions", timeout=3)
        
        if resp.status_code == 200 and t_resp.status_code == 200:
            categories_data = resp.json()
            transactions = t_resp.json()
        else:
            error = f"Backend zwrócił kod: {resp.status_code}"
    except Exception as e:
        error = f"Brak połączenia z backendem: {str(e)}"

    return templates.TemplateResponse(
        "categories.html",
        {
            "request": request, 
            "categories": categories_data, 
            "transactions": transactions,
            "error": error,
            "msg": msg
        }
    )


@app.get("/alerts")
def alerts_page(request: Request):
    error = None
    try:
        response = requests.get(f"{BACKEND_URL}/api/alerts", timeout=5)
        alerts = response.json() if response.status_code == 200 else []
        if response.status_code != 200:
            error = f"Błąd API alertów: {response.status_code}"
    except Exception as e:
        alerts = []
        error = f"Błąd połączenia z backendem: {e}"

    return templates.TemplateResponse(
        "alerts.html",
        {"request": request, "alerts": alerts, "error": error}
    )



@app.post("/transactions/add")
async def add_transaction(request: Request):
    body = (await request.body()).decode("utf-8")
    form_data = urllib.parse.parse_qs(body)

    title = form_data.get("title", [""])[0]
    amount_str = form_data.get("amount", ["0"])[0]
    category_id_str = form_data.get("category_id", ["1"])[0]

    try:
        payload = {
            "title": title,
            "amount": float(amount_str),
            "category_id": int(category_id_str)
        }
        resp = requests.post(f"{BACKEND_URL}/api/transactions", json=payload, timeout=3)
        if resp.status_code == 201:
            return RedirectResponse(url="/?msg=Dodano+nowa+transakcje", status_code=303)
        else:
            detail = resp.json().get("detail", "Błąd walidacji")
            return RedirectResponse(url=f"/?err={urllib.parse.quote(str(detail))}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/?err={urllib.parse.quote(str(e))}", status_code=303)

@app.post("/transactions/delete/{transaction_id}")
def delete_transaction(transaction_id: int):
    try:
        resp = requests.delete(f"{BACKEND_URL}/api/transactions/{transaction_id}", timeout=3)
        if resp.status_code == 200:
            return RedirectResponse(url="/kategorie?msg=Usunieto+transakcje", status_code=303)
    except Exception:
        pass
    return RedirectResponse(url="/kategorie?err=Nie udalo sie usunac transakcji", status_code=303)