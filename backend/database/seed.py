"""模拟数据生成器。

用固定随机种子生成 2024-01 ~ 2025-12 的跨境经营数据，刻意埋入以下叙事线索，
以支撑 capsule 中的验收案例：

    - 美国市场 2025 年下半年销量下滑，8 月出现约 -16% 的环比骤降（Case 3 混合分析）。
    - TikTok Shop 平台 2025 年份额持续走高（Case 4 平台规则与销量）。
    - 中东市场 2025 年高速增长（Case 3 变体：是否符合当地趋势）。
    - 少数 SKU 近 30 天销量高但库存偏低，15 天内可能缺货（Case 5）。
"""

import random
from datetime import date, timedelta

from backend.database.schema import SCHEMA_SQL

# 固定种子，保证每次生成的数据完全一致、可复现
RANDOM_SEED = 20250909

# ---------------------------------------------------------------------------
# 商品
# ---------------------------------------------------------------------------
CATEGORIES = ["性感内衣", "情趣内衣", "COS服饰", "家居服", "睡裙"]

PRODUCT_SPECS = [
    # (sku, name, category, cost, price)
    ("XY-1001", "蕾丝聚拢内衣套装", "性感内衣", 18.0, 45.0),
    ("XY-1002", "无钢圈舒适文胸", "性感内衣", 14.0, 36.0),
    ("XY-1003", "美背镂空内衣", "性感内衣", 16.0, 42.0),
    ("XY-1004", "聚拢调整型内衣", "性感内衣", 20.0, 52.0),
    ("XY-1005", "法式三角杯内衣", "性感内衣", 12.0, 32.0),
    ("XY-1006", "前扣美背文胸", "性感内衣", 15.0, 38.0),
    ("XY-1007", "缎面刺绣内衣", "性感内衣", 24.0, 66.0),
    ("XY-1008", "薄款透纱内衣", "性感内衣", 11.0, 30.0),
    ("XY-1009", "深V聚拢内衣", "性感内衣", 17.0, 44.0),
    ("XY-1010", "运动风无痕内衣", "性感内衣", 13.0, 34.0),
    ("QQ-2001", "蕾丝吊带情趣套装", "情趣内衣", 22.0, 58.0),
    ("QQ-2002", "透视网纱睡裙", "情趣内衣", 19.0, 52.0),
    ("QQ-2003", "皮质束腰套装", "情趣内衣", 28.0, 76.0),
    ("QQ-2004", "角色扮演制服", "情趣内衣", 26.0, 70.0),
    ("QQ-2005", "连体网衣", "情趣内衣", 15.0, 40.0),
    ("QQ-2006", "丝绒吊带套装", "情趣内衣", 21.0, 56.0),
    ("COS-3001", "女仆装套装", "COS服饰", 30.0, 85.0),
    ("COS-3002", "兔女郎套装", "COS服饰", 32.0, 90.0),
    ("COS-3003", "护士装套装", "COS服饰", 29.0, 82.0),
    ("COS-3004", "校园水手服", "COS服饰", 27.0, 75.0),
    ("COS-3005", "天使翅膀套装", "COS服饰", 35.0, 98.0),
    ("JJ-4001", "纯棉家居睡衣", "家居服", 16.0, 42.0),
    ("JJ-4002", "珊瑚绒睡袍", "家居服", 25.0, 68.0),
    ("JJ-4003", "冰丝家居套装", "家居服", 18.0, 48.0),
    ("JJ-4004", "法兰绒两件套", "家居服", 23.0, 62.0),
    ("JJ-4005", "缎面家居袍", "家居服", 22.0, 60.0),
    ("SQ-5001", "真丝吊带睡裙", "睡裙", 26.0, 72.0),
    ("SQ-5002", "蕾丝边睡裙", "睡裙", 20.0, 55.0),
    ("SQ-5003", "纯棉长款睡裙", "睡裙", 15.0, 40.0),
    ("SQ-5004", "冰丝中长睡裙", "睡裙", 17.0, 46.0),
]

# ---------------------------------------------------------------------------
# 店铺：TikTok Shop 10 家矩阵 + 其他平台
# ---------------------------------------------------------------------------
STORE_SPECS = [
    # (store_name, platform, country)
    ("TikTok美国1号店", "TikTok Shop", "美国"),
    ("TikTok美国2号店", "TikTok Shop", "美国"),
    ("TikTok美国3号店", "TikTok Shop", "美国"),
    ("TikTok美国4号店", "TikTok Shop", "美国"),
    ("TikTok美国5号店", "TikTok Shop", "美国"),
    ("TikTok英国1号店", "TikTok Shop", "英国"),
    ("TikTok英国2号店", "TikTok Shop", "英国"),
    ("TikTok中东1号店", "TikTok Shop", "中东"),
    ("TikTok中东2号店", "TikTok Shop", "中东"),
    ("TikTok东南亚店", "TikTok Shop", "中东"),
    ("Amazon美国站", "Amazon", "美国"),
    ("Amazon英国站", "Amazon", "英国"),
    ("Amazon中东站", "Amazon", "中东"),
    ("依伊官方独立站(US)", "独立站", "美国"),
    ("依伊官方独立站(UK)", "独立站", "英国"),
    ("Shein跨境店", "Shein", "美国"),
    ("Shein中东店", "Shein", "中东"),
]

COUNTRIES = ["美国", "英国", "中东"]
PLATFORMS = ["TikTok Shop", "Amazon", "独立站", "Shein"]

# ---------------------------------------------------------------------------
# 国家/平台月度因子：埋入市场叙事
# ---------------------------------------------------------------------------
def _country_factor(country: str, month_index: int) -> float:
    """month_index 为全局月序（0 = 2024-01，11 = 2024-12，12 = 2025-01，23 = 2025-12）。"""
    year2 = month_index >= 12  # 是否为 2025 年
    m = month_index % 12 + 1  # 1-12 月
    if country == "美国":
        if not year2:
            return 1.0
        # 2025 年上半年平稳，6 月起逐步下滑，8 月骤降，11-12 月旺季反弹
        us = {1: 1.05, 2: 1.02, 3: 1.04, 4: 1.00, 5: 0.98,
              6: 0.95, 7: 0.90, 8: 0.74, 9: 0.78, 10: 0.75, 11: 0.92, 12: 1.08}
        return us[m]
    if country == "英国":
        return 0.88 + 0.04 * ((m % 4) == 0)  # 基本平稳
    if country == "中东":
        if not year2:
            return 0.55
        # 2025 年持续高速增长
        me = {1: 0.62, 2: 0.68, 3: 0.75, 4: 0.82, 5: 0.90, 6: 0.95,
              7: 1.00, 8: 1.08, 9: 1.12, 10: 1.18, 11: 1.22, 12: 1.28}
        return me[m]
    return 1.0


def _platform_factor(platform: str, month_index: int) -> float:
    year2 = month_index >= 12
    m = month_index % 12 + 1
    if platform == "TikTok Shop":
        if not year2:
            return 0.65
        # 全年走高，短视频+达人矩阵放量
        base = 0.75 + (m - 1) * 0.05
        return min(base, 1.35)
    if platform == "Amazon":
        if not year2:
            return 1.20
        base = 1.12 - (m - 1) * 0.035
        return max(base, 0.70)
    if platform == "独立站":
        return 0.72
    if platform == "Shein":
        return 0.80
    return 1.0


def _seasonality(m: int) -> float:
    # 1-12 月：淡旺季，11/12 月黑五+圣诞旺季
    wave = {1: 0.85, 2: 0.88, 3: 0.95, 4: 1.00, 5: 1.02, 6: 1.05,
            7: 1.08, 8: 1.02, 9: 0.95, 10: 0.98, 11: 1.22, 12: 1.30}
    return wave[m]


# ---------------------------------------------------------------------------
# 客户
# ---------------------------------------------------------------------------
def _build_customers(rng: random.Random) -> list[dict]:
    customers = []
    cid = 1
    # B 端批发客户
    for i in range(30):
        country = COUNTRIES[i % 3]
        customers.append({
            "customer_id": cid,
            "customer_name": f"{country}B端采购商{chr(65 + i % 26)}{i}",
            "customer_type": "B端",
            "country": country,
            "first_order_date": date(2023, 6, 1) + timedelta(days=rng.randint(0, 400)),
            "last_order_date": date(2024, 1, 1),
        })
        cid += 1
    # C 端消费者
    for i in range(120):
        country = COUNTRIES[i % 3]
        customers.append({
            "customer_id": cid,
            "customer_name": f"C端用户{cid:04d}",
            "customer_type": "C端",
            "country": country,
            "first_order_date": date(2024, 1, 1) + timedelta(days=rng.randint(0, 700)),
            "last_order_date": date(2024, 1, 1),
        })
        cid += 1
    return customers


# ---------------------------------------------------------------------------
# 主构建入口
# ---------------------------------------------------------------------------
def _weighted_pick(rng: random.Random, items: list[str], weights: list[float]) -> str:
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for item, w in zip(items, weights):
        acc += w
        if r <= acc:
            return item
    return items[-1]


def build_database(db_path: str) -> None:
    """建表并写入全部模拟数据。"""
    import sqlite3

    rng = random.Random(RANDOM_SEED)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)

    # ---- 商品 ----
    products = []
    for pid, (sku, name, cat, cost, price) in enumerate(PRODUCT_SPECS, start=1):
        products.append({"product_id": pid, "sku": sku, "product_name": name,
                         "category": cat, "cost": cost, "price": price,
                         "launch_date": "2023-05-01"})
        cur.execute(
            "INSERT INTO product VALUES (?,?,?,?,?,?,?)",
            (pid, sku, name, cat, cost, price, "2023-05-01"),
        )

    # ---- 店铺 ----
    stores = []
    for sid, (sname, plat, country) in enumerate(STORE_SPECS, start=1):
        stores.append({"store_id": sid, "store_name": sname, "platform": plat,
                       "country": country, "opened_date": "2023-08-01"})
        cur.execute(
            "INSERT INTO store VALUES (?,?,?,?,?)",
            (sid, sname, plat, country, "2023-08-01"),
        )

    # ---- 客户 ----
    customers = _build_customers(rng)
    for c in customers:
        cur.execute(
            "INSERT INTO customer VALUES (?,?,?,?,?,?)",
            (c["customer_id"], c["customer_name"], c["customer_type"],
             c["country"], c["first_order_date"].isoformat(), c["last_order_date"].isoformat()),
        )

    # ---- 销售订单：按月生成，遵循国家/平台/季节因子 ----
    orders = []
    oid = 1
    order_id_to_customer = {}
    for month_index in range(24):  # 2024-01 ~ 2025-12
        year = 2024 + (month_index // 12)
        month = month_index % 12 + 1
        month_start = date(year, month, 1)

        # 月订单规模：基准 88 单 × 季节 × 平均国家因子 × 平均平台因子 + 噪声
        avg_country = sum(_country_factor(c, month_index) for c in COUNTRIES) / len(COUNTRIES)
        avg_platform = sum(_platform_factor(p, month_index) for p in PLATFORMS) / len(PLATFORMS)
        base = 88 * _seasonality(month) * avg_country * avg_platform
        n_orders = max(30, int(base * rng.uniform(0.85, 1.15)))

        for _ in range(n_orders):
            country = _weighted_pick(
                rng, COUNTRIES, [_country_factor(c, month_index) for c in COUNTRIES])
            platform = _weighted_pick(
                rng, PLATFORMS, [_platform_factor(p, month_index) for p in PLATFORMS])

            # 选择店铺：优先同平台+同国家
            candidates = [s for s in stores
                          if s["platform"] == platform and s["country"] == country]
            if not candidates:
                candidates = [s for s in stores if s["platform"] == platform]
            store = rng.choice(candidates)

            # 选择商品：性感内衣权重最高
            cat_weights = {"性感内衣": 0.35, "情趣内衣": 0.25, "COS服饰": 0.15,
                           "家居服": 0.13, "睡裙": 0.12}
            prod = rng.choice(products)
            while rng.random() > cat_weights.get(prod["category"], 0.12) * 3:
                prod = rng.choice(products)

            quantity = rng.choices([1, 2, 3, 4, 5, 6], weights=[38, 26, 18, 9, 6, 3])[0]
            unit_price = round(prod["price"] * rng.uniform(0.85, 1.15), 2)
            amount = round(unit_price * quantity, 2)

            # 客户：B 端偶尔整单多件，C 端为主
            cust = rng.choice(customers)
            order_date = month_start + timedelta(days=rng.randint(0, 27))
            order_date = order_date.isoformat()
            orders.append((oid, order_date, cust["customer_id"], store["store_id"],
                           prod["product_id"], country, platform, quantity, unit_price, amount))
            order_id_to_customer[oid] = cust["customer_id"]
            oid += 1

    cur.executemany(
        "INSERT INTO sales_order VALUES (?,?,?,?,?,?,?,?,?,?)", orders)

    # 更新客户最近下单日期
    latest = {}
    for oid, odate, cid, *_ in orders:
        if cid not in latest or odate > latest[cid]:
            latest[cid] = odate
    for cid, odate in latest.items():
        cur.execute("UPDATE customer SET last_order_date=? WHERE customer_id=?", (odate, cid))

    # ---- 库存：先按近 30 天销量推导日均，再刻意构造缺货 SKU ----
    # 近 30 天销量（2025-12）
    sales_30d = {}
    for oid, odate, cid, sid, pid, country, platform, qty, up, amt in orders:
        if odate >= "2025-12-01":
            sales_30d[pid] = sales_30d.get(pid, 0) + qty

    daily_avg = {pid: sales_30d.get(pid, 0) / 30.0 for pid in range(1, len(products) + 1)}

    # 挑选近 30 天销量最高的若干 SKU 作为「即将缺货」候选
    hot_skus = sorted(sales_30d, key=sales_30d.get, reverse=True)[:6]
    shortage_skus = set(hot_skus[:4])  # 4 个热销 SKU 库存刻意压低
    inv_id = 1
    for prod in products:
        pid = prod["product_id"]
        d = daily_avg.get(pid, 0.0)
        if pid in shortage_skus:
            # 库存 = 日均销量 × 8~12 天 → 15 天内必缺货
            stock = int(d * rng.uniform(8, 12)) if d > 0 else 30
        else:
            stock = int(d * rng.uniform(40, 90)) if d > 0 else rng.randint(300, 900)
        stock = max(5, stock)
        safety = int(d * rng.uniform(15, 25)) if d > 0 else 120
        cur.execute(
            "INSERT INTO inventory VALUES (?,?,?,?,?,?)",
            (inv_id, pid, "佛山主仓", stock, safety, "2025-11-15"),
        )
        inv_id += 1

    # ---- 质检：每商品 2025 年若干批次，2%~15% 不合格率 ----
    qid = 1
    high_defect = {5, 9, 16, 21}  # 部分 SKU 不合格率偏高
    for prod in products:
        pid = prod["product_id"]
        for bi in range(6):
            total = rng.randint(800, 2000)
            rate = rng.uniform(0.12, 0.15) if pid in high_defect else rng.uniform(0.02, 0.08)
            defect = int(total * rate)
            insp_date = date(2025, 1 + bi * 2, rng.randint(1, 28)).isoformat()
            cur.execute(
                "INSERT INTO quality_inspection VALUES (?,?,?,?,?,?)",
                (qid, insp_date, pid, f"B{2025}-{pid:02d}-{bi}", total, defect),
            )
            qid += 1

    # ---- 生产延期：2025 年下半年集中 ----
    did = 1
    slow_products = [9, 16, 21, 24, 28]
    for _ in range(70):
        pid = rng.choice(slow_products if rng.random() < 0.6 else [p["product_id"] for p in products])
        planned = date(2025, rng.randint(7, 12), rng.randint(1, 28))
        delay = rng.randint(0, 25)
        actual = planned + timedelta(days=delay)
        cur.execute(
            "INSERT INTO production_delay VALUES (?,?,?,?,?,?)",
            (did, rng.randint(1, oid - 1), pid, planned.isoformat(), actual.isoformat(), delay),
        )
        did += 1

    conn.commit()
    conn.close()


if __name__ == "__main__":
    from backend.config import settings

    build_database(settings.db_path)
    print(f"[seed] 模拟数据已写入 {settings.db_path}")
