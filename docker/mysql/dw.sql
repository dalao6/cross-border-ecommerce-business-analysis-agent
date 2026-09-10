SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS dw DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
GRANT ALL PRIVILEGES ON dw.* TO 'didilili'@'%';
USE dw;

-- ---------------------------------------------------------------------------
-- 依伊服饰跨境经营分析数仓（MySQL 镜像）
-- 结构与 backend/database/schema.py 保持一致；数据为少量示例值，用于同步脚本
-- 读取字段类型（show columns）与字段示例值（select distinct）。
-- 如需完整 24 个月演示数据，请运行 python run.py 生成 SQLite 后自行导入。
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS sales_order;
CREATE TABLE sales_order
(
    order_id    INT PRIMARY KEY,
    order_date  DATE NOT NULL,
    customer_id INT NOT NULL,
    store_id    INT NOT NULL,
    product_id  INT NOT NULL,
    country     VARCHAR(50) NOT NULL,
    platform    VARCHAR(50) NOT NULL,
    quantity    INT NOT NULL,
    unit_price  DECIMAL(10,2) NOT NULL,
    amount      DECIMAL(10,2) NOT NULL
);

DROP TABLE IF EXISTS product;
CREATE TABLE product
(
    product_id   INT PRIMARY KEY,
    sku          VARCHAR(50) NOT NULL,
    product_name VARCHAR(100) NOT NULL,
    category     VARCHAR(50) NOT NULL,
    cost         DECIMAL(10,2) NOT NULL,
    price        DECIMAL(10,2) NOT NULL,
    launch_date  DATE NOT NULL
);

DROP TABLE IF EXISTS store;
CREATE TABLE store
(
    store_id    INT PRIMARY KEY,
    store_name  VARCHAR(100) NOT NULL,
    platform    VARCHAR(50) NOT NULL,
    country     VARCHAR(50) NOT NULL,
    opened_date DATE NOT NULL
);

DROP TABLE IF EXISTS customer;
CREATE TABLE customer
(
    customer_id      INT PRIMARY KEY,
    customer_name    VARCHAR(100) NOT NULL,
    customer_type    VARCHAR(50) NOT NULL,
    country          VARCHAR(50) NOT NULL,
    first_order_date DATE NOT NULL,
    last_order_date  DATE NOT NULL
);

DROP TABLE IF EXISTS inventory;
CREATE TABLE inventory
(
    inventory_id      INT PRIMARY KEY,
    product_id        INT NOT NULL,
    warehouse         VARCHAR(50) NOT NULL,
    quantity          INT NOT NULL,
    safety_stock      INT NOT NULL,
    last_restock_date DATE NOT NULL
);

DROP TABLE IF EXISTS quality_inspection;
CREATE TABLE quality_inspection
(
    inspection_id   INT PRIMARY KEY,
    inspection_date DATE NOT NULL,
    product_id      INT NOT NULL,
    batch           VARCHAR(50) NOT NULL,
    total_qty       INT NOT NULL,
    defect_qty      INT NOT NULL
);

DROP TABLE IF EXISTS production_delay;
CREATE TABLE production_delay
(
    delay_id     INT PRIMARY KEY,
    order_id     INT NOT NULL,
    product_id   INT NOT NULL,
    planned_date DATE NOT NULL,
    actual_date  DATE NOT NULL,
    delay_days   INT NOT NULL
);

-- ---------------------------------------------------------------------------
-- 示例数据（供 get_column_values 提取字段真实取值）
-- ---------------------------------------------------------------------------

INSERT INTO product (product_id, sku, product_name, category, cost, price, launch_date) VALUES
(1, 'XY-1001', '蕾丝聚拢内衣套装', '性感内衣', 18.0, 45.0, '2024-01-15'),
(2, 'QQ-2001', '蕾丝吊带情趣套装', '情趣内衣', 22.0, 58.0, '2024-02-20'),
(3, 'COS-3001', '女仆装套装', 'COS服饰', 30.0, 85.0, '2024-03-10'),
(4, 'JJ-4001', '纯棉家居睡衣', '家居服', 16.0, 42.0, '2024-04-01'),
(5, 'XY-1002', '无钢圈舒适文胸', '性感内衣', 14.0, 36.0, '2024-05-01');

INSERT INTO store (store_id, store_name, platform, country, opened_date) VALUES
(1, 'TikTok 美国店', 'TikTok Shop', '美国', '2024-01-01'),
(2, 'Amazon 美国店', 'Amazon', '美国', '2024-02-01'),
(3, 'Shein 中东店', 'Shein', '中东', '2024-03-01'),
(4, '独立站英国店', '独立站', '英国', '2024-04-01');

INSERT INTO customer (customer_id, customer_name, customer_type, country, first_order_date, last_order_date) VALUES
(1, '北美批发商A', 'B端', '美国', '2024-01-10', '2025-11-20'),
(2, '英国采购商B', 'B端', '英国', '2024-02-15', '2025-12-05'),
(3, '中东分销商C', 'B端', '中东', '2024-03-20', '2025-12-10'),
(4, '个人买家D', 'C端', '美国', '2024-05-01', '2025-08-01');

INSERT INTO inventory (inventory_id, product_id, warehouse, quantity, safety_stock, last_restock_date) VALUES
(1, 1, '深圳仓', 1200, 500, '2025-11-20'),
(2, 2, '深圳仓', 300, 500, '2025-11-15'),
(3, 3, '广州仓', 800, 300, '2025-12-01'),
(4, 4, '广州仓', 150, 300, '2025-11-10');

INSERT INTO quality_inspection (inspection_id, inspection_date, product_id, batch, total_qty, defect_qty) VALUES
(1, '2025-10-01', 1, 'B20251001', 1000, 20),
(2, '2025-10-15', 2, 'B20251015', 800, 45),
(3, '2025-11-01', 3, 'B20251101', 600, 12);

INSERT INTO production_delay (delay_id, order_id, product_id, planned_date, actual_date, delay_days) VALUES
(1, 1001, 2, '2025-10-10', '2025-10-18', 8),
(2, 1002, 4, '2025-11-01', '2025-11-12', 11),
(3, 1003, 3, '2025-11-20', '2025-11-25', 5);

INSERT INTO sales_order (order_id, order_date, customer_id, store_id, product_id, country, platform, quantity, unit_price, amount) VALUES
(1001, '2025-08-01', 1, 2, 1, '美国', 'Amazon', 100, 45.0, 4500.0),
(1002, '2025-08-15', 1, 2, 2, '美国', 'Amazon', 80, 58.0, 4640.0),
(1003, '2025-09-01', 2, 1, 1, '英国', 'TikTok Shop', 120, 45.0, 5400.0),
(1004, '2025-09-15', 3, 3, 3, '中东', 'Shein', 60, 85.0, 5100.0);
