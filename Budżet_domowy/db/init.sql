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