CREATE TABLE IF NOT EXISTS stats (
    key TEXT PRIMARY KEY,
    val INT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('income', 'expense'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    amount NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    category_id INT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_history (
    id SERIAL PRIMARY KEY,
    transaction_id INT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    action VARCHAR(20) NOT NULL CHECK (action IN ('CREATE', 'UPDATE', 'DELETE')),
    changed_by VARCHAR(100) NOT NULL DEFAULT 'System',
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    details TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    message TEXT NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO categories (name, type) VALUES
    ('Wynagrodzenie', 'income'),
    ('Mieszkanie', 'expense'),
    ('Jedzenie', 'expense'),
    ('Rozrywka', 'expense');

INSERT INTO transactions (title, amount, category_id) VALUES
    ('Pensja podstawowa', 3000.00, 1),
    ('Czynsz i media', 1600.00, 2),
    ('Zakupy spożywcze', 500.00, 3),
    ('Wyjście do kina', 100.00, 4);

INSERT INTO transaction_history (transaction_id, action, changed_by, details) VALUES
    (1, 'CREATE', 'Inicjalizacja systemu', 'Dodano transakcję: Pensja podstawowa (3000.00 PLN, kategoria ID: 1)'),
    (2, 'CREATE', 'Inicjalizacja systemu', 'Dodano transakcję: Czynsz i media (1600.00 PLN, kategoria ID: 2)'),
    (3, 'CREATE', 'Inicjalizacja systemu', 'Dodano transakcję: Zakupy spożywcze (500.00 PLN, kategoria ID: 3)'),
    (4, 'CREATE', 'Inicjalizacja systemu', 'Dodano transakcję: Wyjście do kina (100.00 PLN, kategoria ID: 4)');