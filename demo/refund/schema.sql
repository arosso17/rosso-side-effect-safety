PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    operation_id TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS refunds_order_id_idx ON refunds(order_id);
