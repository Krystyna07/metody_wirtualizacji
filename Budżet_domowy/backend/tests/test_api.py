import os
import requests

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


def test_healthcheck():
    resp = requests.get(f"{BASE_URL}/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"


def test_get_transactions_list():
    resp = requests.get(f"{BASE_URL}/api/transactions", timeout=5)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_transaction_validation_errors_400():
    # Pusta nazwa
    r1 = requests.post(
        f"{BASE_URL}/api/transactions",
        json={"title": "   ", "amount": 50.0, "category_id": 1},
        timeout=5
    )
    assert r1.status_code == 400

    # Ujemna kwota
    r2 = requests.post(
        f"{BASE_URL}/api/transactions",
        json={"title": "Test", "amount": -10.0, "category_id": 1},
        timeout=5
    )
    assert r2.status_code == 400

    # Nieistniejąca kategoria
    r3 = requests.post(
        f"{BASE_URL}/api/transactions",
        json={"title": "Test", "amount": 25.0, "category_id": 999999},
        timeout=5
    )
    assert r3.status_code == 400

    # Brak wymaganego pola JSON
    r4 = requests.post(
        f"{BASE_URL}/api/transactions",
        json={"title": "Brak kwoty"},
        timeout=5
    )
    assert r4.status_code == 400


def test_get_single_transaction_not_found_404():
    resp = requests.get(f"{BASE_URL}/api/transactions/999999", timeout=5)
    assert resp.status_code == 404


def test_update_and_delete_not_found_404():
    r_put = requests.put(
        f"{BASE_URL}/api/transactions/999999",
        json={"title": "Nie ma", "amount": 100.0, "category_id": 1},
        timeout=5
    )
    assert r_put.status_code == 404

    r_del = requests.delete(f"{BASE_URL}/api/transactions/999999", timeout=5)
    assert r_del.status_code == 404


def test_full_crud_and_client_history_audit():
    # 1. POST - utworzenie rekordu z informacją kto dodał
    create_resp = requests.post(
        f"{BASE_URL}/api/transactions",
        json={"title": "Testowy zakup", "amount": 120.50, "category_id": 3},
        headers={"X-User": "Tester_Krysia"},
        timeout=5
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    tx_id = created["id"]
    assert created["title"] == "Testowy zakup"

    # 2. GET pojedynczego zasobu
    get_resp = requests.get(f"{BASE_URL}/api/transactions/{tx_id}", timeout=5)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == tx_id

    # 3. PUT - aktualizacja rekordu i zapis w historii
    put_resp = requests.put(
        f"{BASE_URL}/api/transactions/{tx_id}",
        json={"title": "Testowy zakup po korekcie", "amount": 150.00, "category_id": 3},
        headers={"X-User": "Audytor_Jan"},
        timeout=5
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["amount"] == 150.0

    # Walidacja błędu 400 przy PUT
    bad_put = requests.put(
        f"{BASE_URL}/api/transactions/{tx_id}",
        json={"title": "", "amount": 150.00, "category_id": 3},
        timeout=5
    )
    assert bad_put.status_code == 400

    # 4. PATCH - częściowa aktualizacja rekordu
    patch_resp = requests.patch(
        f"{BASE_URL}/api/transactions/{tx_id}",
        json={"amount": 175.00},
        headers={"X-User": "Audytor_Anna"},
        timeout=5
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["amount"] == 175.0

    # 5. DELETE - miękkie usunięcie rekordu i zapis w historii
    del_resp = requests.delete(
        f"{BASE_URL}/api/transactions/{tx_id}",
        headers={"X-User": "Admin_Piotr"},
        timeout=5
    )
    assert del_resp.status_code == 200

    # Po usunięciu GET pojedynczego zasobu zwraca 404
    after_del_get = requests.get(f"{BASE_URL}/api/transactions/{tx_id}", timeout=5)
    assert after_del_get.status_code == 404

    # 6. GET /api/transactions/{id}/history - weryfikacja pełnej historii zmian (CREATE, UPDATE, DELETE)
    hist_resp = requests.get(f"{BASE_URL}/api/transactions/{tx_id}/history", timeout=5)
    assert hist_resp.status_code == 200
    history = hist_resp.json()
    assert len(history) == 4

    assert history[0]["action"] == "CREATE"
    assert history[0]["changed_by"] == "Tester_Krysia"
    assert history[0]["changed_at"] is not None

    assert history[1]["action"] == "UPDATE"
    assert history[1]["changed_by"] == "Audytor_Jan"

    assert history[2]["action"] == "UPDATE"
    assert history[2]["changed_by"] == "Audytor_Anna"

    assert history[3]["action"] == "DELETE"
    assert history[3]["changed_by"] == "Admin_Piotr"


def test_history_not_found_404():
    resp = requests.get(f"{BASE_URL}/api/transactions/999999/history", timeout=5)
    assert resp.status_code == 404