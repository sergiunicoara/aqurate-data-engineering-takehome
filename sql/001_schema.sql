CREATE TABLE IF NOT EXISTS orders_raw (
    source_hash TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    order_id_raw TEXT,
    customer_id_raw TEXT,
    customer_email_raw TEXT,
    order_ts_raw TEXT,
    status_raw TEXT,
    channel_raw TEXT,
    sku_raw TEXT,
    product_name_raw TEXT,
    category_raw TEXT,
    qty_raw TEXT,
    unit_price_raw TEXT,
    currency_raw TEXT,
    country_raw TEXT,
    fx_reference_date_raw TEXT,
    source_loaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders_clean (
    source_hash TEXT PRIMARY KEY REFERENCES orders_raw(source_hash),
    order_id TEXT NOT NULL,
    customer_id INTEGER,
    customer_email TEXT,
    order_ts TEXT NOT NULL,
    status TEXT NOT NULL,
    channel TEXT,
    sku TEXT,
    product_name TEXT,
    category TEXT NOT NULL,
    qty INTEGER NOT NULL CHECK(qty >= 0),
    unit_price NUMERIC NOT NULL CHECK(unit_price >= 0),
    line_amount NUMERIC NOT NULL CHECK(line_amount >= 0),
    currency TEXT NOT NULL,
    country TEXT NOT NULL,
    fx_reference_date TEXT NOT NULL,
    cleaning_notes TEXT NOT NULL,
    cleaned_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rejected_orders (
    source_hash TEXT PRIMARY KEY REFERENCES orders_raw(source_hash),
    rejection_reason TEXT NOT NULL,
    rejected_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fx_rates (
    rate_date TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    rate NUMERIC NOT NULL CHECK(rate > 0),
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (rate_date, base_currency, quote_currency)
);

CREATE TABLE IF NOT EXISTS order_values_eur (
    source_hash TEXT PRIMARY KEY REFERENCES orders_clean(source_hash),
    order_id TEXT NOT NULL,
    customer_id INTEGER,
    country TEXT NOT NULL,
    category TEXT NOT NULL,
    original_amount NUMERIC NOT NULL,
    original_currency TEXT NOT NULL,
    fx_reference_date TEXT NOT NULL,
    fx_rate_date_used TEXT,
    fx_rate_used NUMERIC,
    amount_eur NUMERIC,
    calculated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customer_spend_eur (
    customer_id INTEGER PRIMARY KEY,
    total_spend_eur NUMERIC NOT NULL,
    order_count INTEGER NOT NULL,
    last_refreshed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS country_category_revenue (
    revenue_rank INTEGER NOT NULL,
    country TEXT PRIMARY KEY,
    total_revenue_eur NUMERIC NOT NULL,
    order_count INTEGER NOT NULL,
    last_refreshed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('running', 'succeeded', 'failed')),
    raw_rows INTEGER DEFAULT 0,
    clean_rows INTEGER DEFAULT 0,
    rejected_rows INTEGER DEFAULT 0,
    fx_rows_added INTEGER DEFAULT 0,
    missing_fx_orders INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_fx_lookup ON fx_rates(base_currency, quote_currency, rate_date);
CREATE INDEX IF NOT EXISTS ix_clean_customer ON orders_clean(customer_id);

