import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests

app = FastAPI(title="Budzet domowy - frontend")
templates = Jinja2Templates(directory="app/templates")

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")

@app.get("/", response_class=HTMLResponse)
def read_index(request:Request):
    data = {}
    error = None
    try:
        resp = requests.get(f"{BACKEND_URL}/api/budget/summary", timeout=3)

        if resp.status_code == 200:
            data = resp.json()
        else:
            error = f"Backend zwrocil kod: {resp.status_code}"
    except Exception as e:
        error = f"Brak polaczenia z backendem: {str(e)}"

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "budget": data, "error":error}
    )