"""建表 SQL（SQLite 方言）。

表结构对齐 capsule 规格中的跨境电商经营分析场景：
销售订单（事实）、商品/店铺/客户（维度）、库存/质检/生产延期（供应链）。
"""

SCHEMA_SQL = """
DROP TABLE IF EXISTS sales_order;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS store;
DROP TABLE IF EXISTS customer;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS quality_inspection;
DROP TABLE IF EXISTS production_delay;

CREATE TABLE product (
    product_id   INTEGER PRIMARY KEY,
    sku          TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL,
    cost         REAL NOT NULL,
    price        REAL NOT NULL,
    launch_date  TEXT NOT NULL
);

CREATE TABLE store (
    store_id    INTEGER PRIMARY KEY,
    store_name  TEXT NOT NULL,
    platform    TEXT NOT NULL,
    country     TEXT NOT NULL,
    opened_date TEXT NOT NULL
);

CREATE TABLE customer (
    customer_id      INTEGER PRIMARY KEY,
    customer_name    TEXT NOT NULL,
    customer_type    TEXT NOT NULL,
    country          TEXT NOT NULL,
    first_order_date TEXT NOT NULL,
    last_order_date  TEXT NOT NULL
);

CREATE TABLE sales_order (
    order_id    INTEGER PRIMARY KEY,
    order_date  TEXT NOT NULL,
    customer_id INTEGER NOT NULL,
    store_id    INTEGER NOT NULL,
    product_id  INTEGER NOT NULL,
    country     TEXT NOT NULL,
    platform    TEXT NOT NULL,
    quantity    INTEGER NOT NULL,
    unit_price  REAL NOT NULL,
    amount      REAL NOT NULL
);

CREATE TABLE inventory (
    inventory_id      INTEGER PRIMARY KEY,
    product_id        INTEGER NOT NULL,
    warehouse         TEXT NOT NULL,
    quantity          INTEGER NOT NULL,
    safety_stock      INTEGER NOT NULL,
    last_restock_date TEXT NOT NULL
);

CREATE TABLE quality_inspection (
    inspection_id   INTEGER PRIMARY KEY,
    inspection_date TEXT NOT NULL,
    product_id      INTEGER NOT NULL,
    batch           TEXT NOT NULL,
    total_qty       INTEGER NOT NULL,
    defect_qty      INTEGER NOT NULL
);

CREATE TABLE production_delay (
    delay_id     INTEGER PRIMARY KEY,
    order_id     INTEGER NOT NULL,
    product_id   INTEGER NOT NULL,
    planned_date TEXT NOT NULL,
    actual_date  TEXT NOT NULL,
    delay_days   INTEGER NOT NULL
);

CREATE INDEX idx_order_date ON sales_order(order_date);
CREATE INDEX idx_order_country ON sales_order(country);
CREATE INDEX idx_order_platform ON sales_order(platform);
CREATE INDEX idx_order_product ON sales_order(product_id);
CREATE INDEX idx_order_store ON sales_order(store_id);
"""
