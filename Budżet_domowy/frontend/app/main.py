import os
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import requests

app = FastAPI(title="Budżet domowy - frontend")
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
    archived_transactions = []
    error = err
    try:
        resp = requests.get(f"{BACKEND_URL}/api/categories", timeout=3)
        t_resp = requests.get(f"{BACKEND_URL}/api/transactions", timeout=3)
        a_resp = requests.get(f"{BACKEND_URL}/api/transactions/archived", timeout=3)

        if resp.status_code == 200 and t_resp.status_code == 200:
            categories_data = resp.json()
            transactions = t_resp.json()
            archived_transactions = a_resp.json() if a_resp.status_code == 200 else []
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
            "archived_transactions": archived_transactions,
            "error": error,
            "msg": msg
        }
    )


@app.get("/transactions/{transaction_id}/edit", response_class=HTMLResponse)
def edit_transaction_page(request: Request, transaction_id: int, err: str = None):
    transaction = None
    categories = []
    error = err
    try:
        t_resp = requests.get(f"{BACKEND_URL}/api/transactions/{transaction_id}", timeout=3)
        c_resp = requests.get(f"{BACKEND_URL}/api/categories", timeout=3)
        if t_resp.status_code == 200 and c_resp.status_code == 200:
            transaction = t_resp.json()
            categories = c_resp.json()
        else:
            error = f"Nie znaleziono transakcji o ID {transaction_id}"
    except Exception as e:
        error = f"Błąd połączenia z backendem: {str(e)}"

    return templates.TemplateResponse(
        "edit_transaction.html",
        {
            "request": request,
            "transaction": transaction,
            "categories": categories,
            "error": error
        }
    )


@app.post("/transactions/edit/{transaction_id}")
async def update_transaction_submit(transaction_id: int, request: Request):
    body = (await request.body()).decode("utf-8")
    form_data = urllib.parse.parse_qs(body)

    title = form_data.get("title", [""])[0]
    amount_str = form_data.get("amount", ["0"])[0]
    category_id_str = form_data.get("category_id", ["1"])[0]
    changed_by = form_data.get("changed_by", ["Użytkownik"])[0]

    try:
        payload = {
            "title": title,
            "amount": float(amount_str),
            "category_id": int(category_id_str),
            "changed_by": changed_by
        }
        resp = requests.put(
            f"{BACKEND_URL}/api/transactions/{transaction_id}",
            json=payload,
            headers={"X-User": changed_by},
            timeout=3
        )
        if resp.status_code == 200:
            return RedirectResponse(url="/kategorie?msg=Zaktualizowano+transakcje+i+zapisano+historie", status_code=303)
        detail = resp.json().get("detail", "Błąd walidacji")
        return RedirectResponse(
            url=f"/transactions/{transaction_id}/edit?err={urllib.parse.quote(str(detail))}",
            status_code=303
        )
    except Exception as e:
        return RedirectResponse(
            url=f"/transactions/{transaction_id}/edit?err={urllib.parse.quote(str(e))}",
            status_code=303
        )


@app.get("/transactions/{transaction_id}/history", response_class=HTMLResponse)
def transaction_history_page(request: Request, transaction_id: int):
    history = []
    error = None
    try:
        resp = requests.get(f"{BACKEND_URL}/api/transactions/{transaction_id}/history", timeout=3)
        if resp.status_code == 200:
            history = resp.json()
        else:
            error = resp.json().get("detail", f"Błąd pobierania historii ({resp.status_code})")
    except Exception as e:
        error = f"Błąd połączenia z backendem: {str(e)}"

    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "transaction_id": transaction_id,
            "history": history,
            "error": error
        }
    )


@app.get("/alerts", response_class=HTMLResponse)
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
    changed_by = form_data.get("changed_by", ["Użytkownik"])[0]

    try:
        payload = {
            "title": title,
            "amount": float(amount_str),
            "category_id": int(category_id_str),
            "changed_by": changed_by
        }
        resp = requests.post(
            f"{BACKEND_URL}/api/transactions",
            json=payload,
            headers={"X-User": changed_by},
            timeout=3
        )
        if resp.status_code == 201:
            return RedirectResponse(url="/?msg=Dodano+nowa+transakcje", status_code=303)
        detail = resp.json().get("detail", "Błąd walidacji")
        return RedirectResponse(url=f"/?err={urllib.parse.quote(str(detail))}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/?err={urllib.parse.quote(str(e))}", status_code=303)


@app.post("/transactions/delete/{transaction_id}")
async def delete_transaction(transaction_id: int, request: Request):
    body = (await request.body()).decode("utf-8")
    form_data = urllib.parse.parse_qs(body)
    changed_by = form_data.get("changed_by", ["Użytkownik"])[0]

    try:
        resp = requests.delete(
            f"{BACKEND_URL}/api/transactions/{transaction_id}",
            headers={"X-User": changed_by},
            timeout=3
        )
        if resp.status_code == 200:
            return RedirectResponse(
                url="/kategorie?msg=Przeniesiono+transakcje+do+archiwum+i+zapisano+historie",
                status_code=303
            )
    except Exception:
        pass
    return RedirectResponse(url="/kategorie?err=Nie+udalo+sie+usunac+transakcji", status_code=303)