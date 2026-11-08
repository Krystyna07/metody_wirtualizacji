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
    transactions = []
    categories = []
    error = err
    try:
        resp = requests.get(f"{BACKEND_URL}/api/budget/summary", timeout=3)
        t_resp = requests.get(f"{BACKEND_URL}/api/transactions", timeout=3)
        c_resp = requests.get(f"{BACKEND_URL}/api/categories", timeout=3)

        if resp.status_code == 200 and t_resp.status_code == 200 and c_resp.status_code == 200:
            data = resp.json()
            transactions = t_resp.json()
            categories = c_resp.json()
        else:
            error = f"Backend zwrocil blad ({resp.status_code})"
    except Exception as e:
        error = f"Brak polaczenia z backendem: {str(e)}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "budget": data,
            "transactions": transactions,
            "categories": categories,
            "error": error,
            "msg": msg
        }
    )

@app.get("/kategorie", response_class=HTMLResponse)
def read_categories(request: Request):
    categories_data = []
    error = None
    try:
        resp = requests.get(f"{BACKEND_URL}/api/categories", timeout=3)
        if resp.status_code == 200:

            categories_data = [c for c in resp.json() if c.get("type") == "expense"]
        else:
            error = f"Backend zwrócił kod: {resp.status_code}"
    except Exception as e:
        error = f"Brak połączenia z backendem: {str(e)}"

    return templates.TemplateResponse(
        "categories.html",
        {"request": request, "categories": categories_data, "error": error}
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
        requests.delete(f"{BACKEND_URL}/api/transactions/{transaction_id}", timeout=3)
    except Exception:
        pass
    return RedirectResponse(url="/?msg=Usunieto+transakcje", status_code=303)