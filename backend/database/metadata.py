"""元数据字典。

这是「Table Recall / Schema Recall / Metric Recall」三路召回的权威依据。
设计目标：让 NL2SQL 不凭 LLM 经验猜表，而是从这里的结构化元数据中召回
表、字段与指标口径。所有同义词（synonyms）都用于提升中文问法的召回命中率。

对应胶囊规格第十节「数据库元数据设计」：
    - table_metadata
    - column_metadata
    - metric_metadata
"""

# ---------------------------------------------------------------------------
# 表级元数据
# ---------------------------------------------------------------------------
TABLE_METADATA = [
    {
        "table_name": "sales_order",
        "table_comment": "销售订单表",
        "business_domain": "销售",
        "business_description": "记录企业跨境销售订单，包含订单时间、客户、店铺、平台、国家、商品数量与金额。",
        "data_owner": "销售数据组",
        "update_frequency": "每日",
        "synonyms": ["订单", "销售订单", "订单表", "销量", "销售额", "成交", "销售"],
    },
    {
        "table_name": "product",
        "table_comment": "商品表",
        "business_domain": "商品",
        "business_description": "商品（SKU）主数据，包含品类、成本、售价与上架时间。",
        "data_owner": "商品数据组",
        "update_frequency": "每日",
        "synonyms": ["商品", "产品", "SKU", "货品", "款式"],
    },
    {
        "table_name": "store",
        "table_comment": "店铺表",
        "business_domain": "店铺",
        "business_description": "跨境销售店铺主数据，包含平台、站点国家与开店时间。",
        "data_owner": "店铺数据组",
        "update_frequency": "每日",
        "synonyms": ["店铺", "店", "店铺矩阵", "门店"],
    },
    {
        "table_name": "customer",
        "table_comment": "客户表",
        "business_domain": "客户",
        "business_description": "B端/C端客户主数据，包含客户类型、国家与首次/最近下单时间。",
        "data_owner": "客户数据组",
        "update_frequency": "每日",
        "synonyms": ["客户", "买家", "采购商", "用户"],
    },
    {
        "table_name": "inventory",
        "table_comment": "库存表",
        "business_domain": "库存",
        "business_description": "各商品在各仓库的当前库存与安全库存水位。",
        "data_owner": "供应链数据组",
        "update_frequency": "实时",
        "synonyms": ["库存", "存货", "库存量", "备货"],
    },
    {
        "table_name": "quality_inspection",
        "table_comment": "质检表",
        "business_domain": "供应链",
        "business_description": "生产批次质检记录，包含检验数量与不合格数量。",
        "data_owner": "品控数据组",
        "update_frequency": "每日",
        "synonyms": ["质检", "品控", "不合格率", "退货", "次品"],
    },
    {
        "table_name": "production_delay",
        "table_comment": "生产延期表",
        "business_domain": "供应链",
        "business_description": "生产/交付延期记录，包含计划与实际的交付日期及延期天数。",
        "data_owner": "供应链数据组",
        "update_frequency": "每日",
        "synonyms": ["生产", "延期", "交付", "交期", "产能"],
    },
]

# ---------------------------------------------------------------------------
# 字段级元数据
# ---------------------------------------------------------------------------
COLUMN_METADATA = [
    # ---- sales_order ----
    {"table_name": "sales_order", "column_name": "order_id", "column_comment": "订单ID",
     "business_meaning": "订单唯一标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["订单号", "订单编号"]},
    {"table_name": "sales_order", "column_name": "order_date", "column_comment": "订单日期",
     "business_meaning": "订单创建日期", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["日期", "时间", "下单时间", "月份", "月", "年"]},
    {"table_name": "sales_order", "column_name": "customer_id", "column_comment": "客户ID",
     "business_meaning": "下单客户标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["客户", "买家"]},
    {"table_name": "sales_order", "column_name": "store_id", "column_comment": "店铺ID",
     "business_meaning": "成交店铺标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["店铺", "店"]},
    {"table_name": "sales_order", "column_name": "product_id", "column_comment": "商品ID",
     "business_meaning": "售出商品标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["商品", "产品", "SKU", "款式"]},
    {"table_name": "sales_order", "column_name": "country", "column_comment": "国家/地区",
     "business_meaning": "销售目的国/市场", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["国家", "地区", "市场", "美国", "英国", "中东"]},
    {"table_name": "sales_order", "column_name": "platform", "column_comment": "销售平台",
     "business_meaning": "订单来源平台", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["平台", "渠道", "TikTok", "TikTok Shop", "亚马逊", "Amazon", "独立站", "Shein"]},
    {"table_name": "sales_order", "column_name": "quantity", "column_comment": "销售数量",
     "business_meaning": "商品销售数量（件）", "data_type": "INT", "is_dimension": False, "is_measure": True,
     "synonyms": ["销量", "销售数量", "卖出数量", "商品数量", "件数", "售出"]},
    {"table_name": "sales_order", "column_name": "unit_price", "column_comment": "成交单价",
     "business_meaning": "单件成交价", "data_type": "DECIMAL", "is_dimension": False, "is_measure": True,
     "synonyms": ["单价", "价格", "售价"]},
    {"table_name": "sales_order", "column_name": "amount", "column_comment": "销售金额",
     "business_meaning": "订单成交金额（数量×单价）", "data_type": "DECIMAL", "is_dimension": False, "is_measure": True,
     "synonyms": ["销售额", "销售金额", "GMV", "成交额", "营收", "收入"]},

    # ---- product ----
    {"table_name": "product", "column_name": "product_id", "column_comment": "商品ID",
     "business_meaning": "商品唯一标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["商品", "产品", "SKU"]},
    {"table_name": "product", "column_name": "sku", "column_comment": "SKU编码",
     "business_meaning": "商品库存编码", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["SKU", "编码", "货号"]},
    {"table_name": "product", "column_name": "product_name", "column_comment": "商品名称",
     "business_meaning": "商品名称", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["商品名", "品名", "名称"]},
    {"table_name": "product", "column_name": "category", "column_comment": "品类",
     "business_meaning": "商品所属品类", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["类目", "品类", "分类", "性感内衣", "情趣内衣", "COS", "家居服", "睡裙"]},
    {"table_name": "product", "column_name": "cost", "column_comment": "成本单价",
     "business_meaning": "单件生产成本", "data_type": "DECIMAL", "is_dimension": False, "is_measure": True,
     "synonyms": ["成本", "成本价", "生产成本"]},
    {"table_name": "product", "column_name": "price", "column_comment": "售价",
     "business_meaning": "标准零售价", "data_type": "DECIMAL", "is_dimension": False, "is_measure": True,
     "synonyms": ["价格", "售价", "单价"]},
    {"table_name": "product", "column_name": "launch_date", "column_comment": "上架日期",
     "business_meaning": "商品首次上架日期", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["上架", "上新", "上市"]},

    # ---- store ----
    {"table_name": "store", "column_name": "store_id", "column_comment": "店铺ID",
     "business_meaning": "店铺唯一标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["店铺", "店"]},
    {"table_name": "store", "column_name": "store_name", "column_comment": "店铺名称",
     "business_meaning": "店铺名称", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["店铺名", "店名"]},
    {"table_name": "store", "column_name": "platform", "column_comment": "平台",
     "business_meaning": "店铺所属平台", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["平台", "渠道", "TikTok Shop", "Amazon", "独立站", "Shein"]},
    {"table_name": "store", "column_name": "country", "column_comment": "站点国家",
     "business_meaning": "店铺面向的国家/市场", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["国家", "市场", "站点"]},
    {"table_name": "store", "column_name": "opened_date", "column_comment": "开店日期",
     "business_meaning": "店铺开业日期", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["开店", "上线"]},

    # ---- customer ----
    {"table_name": "customer", "column_name": "customer_id", "column_comment": "客户ID",
     "business_meaning": "客户唯一标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["客户", "买家"]},
    {"table_name": "customer", "column_name": "customer_name", "column_comment": "客户名称",
     "business_meaning": "客户名称", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["客户名", "买家名"]},
    {"table_name": "customer", "column_name": "customer_type", "column_comment": "客户类型",
     "business_meaning": "B端批发客户或C端消费者", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["类型", "B端", "C端", "批发", "零售"]},
    {"table_name": "customer", "column_name": "country", "column_comment": "国家",
     "business_meaning": "客户所在国家", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["国家", "地区", "市场"]},
    {"table_name": "customer", "column_name": "first_order_date", "column_comment": "首次下单日期",
     "business_meaning": "客户首次下单时间", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["首单", "首次下单"]},
    {"table_name": "customer", "column_name": "last_order_date", "column_comment": "最近下单日期",
     "business_meaning": "客户最近一次下单时间", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["最近下单", "末次下单"]},

    # ---- inventory ----
    {"table_name": "inventory", "column_name": "inventory_id", "column_comment": "库存记录ID",
     "business_meaning": "库存记录唯一标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["库存记录"]},
    {"table_name": "inventory", "column_name": "product_id", "column_comment": "商品ID",
     "business_meaning": "商品标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["商品", "产品", "SKU"]},
    {"table_name": "inventory", "column_name": "warehouse", "column_comment": "仓库",
     "business_meaning": "库存所在仓库", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["仓库", "仓"]},
    {"table_name": "inventory", "column_name": "quantity", "column_comment": "库存数量",
     "business_meaning": "当前库存件数", "data_type": "INT", "is_dimension": False, "is_measure": True,
     "synonyms": ["库存", "库存量", "现存", "库存数量"]},
    {"table_name": "inventory", "column_name": "safety_stock", "column_comment": "安全库存",
     "business_meaning": "安全库存水位", "data_type": "INT", "is_dimension": False, "is_measure": True,
     "synonyms": ["安全库存", "警戒线"]},
    {"table_name": "inventory", "column_name": "last_restock_date", "column_comment": "最近入库日期",
     "business_meaning": "最近一次补货入库日期", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["入库", "补货", "进货"]},

    # ---- quality_inspection ----
    {"table_name": "quality_inspection", "column_name": "inspection_id", "column_comment": "质检单ID",
     "business_meaning": "质检单唯一标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["质检单", "检验单"]},
    {"table_name": "quality_inspection", "column_name": "inspection_date", "column_comment": "质检日期",
     "business_meaning": "质检执行日期", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["日期", "质检时间"]},
    {"table_name": "quality_inspection", "column_name": "product_id", "column_comment": "商品ID",
     "business_meaning": "被检商品", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["商品", "产品", "SKU"]},
    {"table_name": "quality_inspection", "column_name": "batch", "column_comment": "批次",
     "business_meaning": "生产批次号", "data_type": "VARCHAR", "is_dimension": True, "is_measure": False,
     "synonyms": ["批次", "批号"]},
    {"table_name": "quality_inspection", "column_name": "total_qty", "column_comment": "检验数量",
     "business_meaning": "本批次检验总数", "data_type": "INT", "is_dimension": False, "is_measure": True,
     "synonyms": ["检验数", "抽检数"]},
    {"table_name": "quality_inspection", "column_name": "defect_qty", "column_comment": "不合格数量",
     "business_meaning": "本批次不合格数", "data_type": "INT", "is_dimension": False, "is_measure": True,
     "synonyms": ["不合格", "次品数", "不良品"]},

    # ---- production_delay ----
    {"table_name": "production_delay", "column_name": "delay_id", "column_comment": "延期记录ID",
     "business_meaning": "延期记录唯一标识", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["延期记录"]},
    {"table_name": "production_delay", "column_name": "order_id", "column_comment": "订单ID",
     "business_meaning": "关联订单", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["订单"]},
    {"table_name": "production_delay", "column_name": "product_id", "column_comment": "商品ID",
     "business_meaning": "延期商品", "data_type": "INT", "is_dimension": True, "is_measure": False,
     "synonyms": ["商品", "产品", "SKU"]},
    {"table_name": "production_delay", "column_name": "planned_date", "column_comment": "计划交付日期",
     "business_meaning": "计划交付日期", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["计划交付", "计划日期", "交期"]},
    {"table_name": "production_delay", "column_name": "actual_date", "column_comment": "实际交付日期",
     "business_meaning": "实际交付日期", "data_type": "DATE", "is_dimension": True, "is_measure": False,
     "synonyms": ["实际交付", "实际日期"]},
    {"table_name": "production_delay", "column_name": "delay_days", "column_comment": "延期天数",
     "business_meaning": "实际交付晚于计划的天数", "data_type": "INT", "is_dimension": False, "is_measure": True,
     "synonyms": ["延期天数", "延误天数", "延期"]},
]

# ---------------------------------------------------------------------------
# 指标级元数据
# ---------------------------------------------------------------------------
METRIC_METADATA = [
    {
        "metric_name": "销量",
        "metric_definition": "统计周期内售出的商品件数之和。",
        "formula": "SUM(sales_order.quantity)",
        "related_tables": ["sales_order"],
        "related_columns": ["quantity"],
        "business_domain": "销售",
        "synonyms": ["销量", "销售数量", "卖出数量", "件数", "售出量"],
    },
    {
        "metric_name": "销售额",
        "metric_definition": "统计周期内订单成交金额之和，即 GMV。",
        "formula": "SUM(sales_order.amount)",
        "related_tables": ["sales_order"],
        "related_columns": ["amount"],
        "business_domain": "销售",
        "synonyms": ["销售额", "销售金额", "GMV", "成交额", "营收", "收入"],
    },
    {
        "metric_name": "客单价",
        "metric_definition": "统计周期内销售额 / 订单数。",
        "formula": "SUM(amount) / COUNT(DISTINCT order_id)",
        "related_tables": ["sales_order"],
        "related_columns": ["amount", "order_id"],
        "business_domain": "销售",
        "synonyms": ["客单价", "单均", "平均每单"],
    },
    {
        "metric_name": "毛利率",
        "metric_definition": "(销售额 - 商品成本) / 销售额。",
        "formula": "(SUM(sales_order.amount) - SUM(product.cost * sales_order.quantity)) / SUM(sales_order.amount)",
        "related_tables": ["sales_order", "product"],
        "related_columns": ["amount", "quantity", "cost"],
        "business_domain": "销售",
        "synonyms": ["毛利率", "毛利"],
    },
    {
        "metric_name": "利润",
        "metric_definition": "销售额 - 商品成本。",
        "formula": "SUM(sales_order.amount) - SUM(product.cost * sales_order.quantity)",
        "related_tables": ["sales_order", "product"],
        "related_columns": ["amount", "quantity", "cost"],
        "business_domain": "销售",
        "synonyms": ["利润", "毛利额", "净赚"],
    },
    {
        "metric_name": "复购率",
        "metric_definition": "统计周期内下单次数>=2次的客户数 / 下单客户总数。",
        "formula": "COUNT(DISTINCT CASE WHEN cnt>=2 THEN customer_id END) / COUNT(DISTINCT customer_id)",
        "related_tables": ["sales_order", "customer"],
        "related_columns": ["customer_id", "order_id"],
        "business_domain": "客户",
        "synonyms": ["复购率", "回购率", "回头客"],
    },
    {
        "metric_name": "质检不合格率",
        "metric_definition": "不合格数量 / 检验总数。",
        "formula": "SUM(defect_qty) / SUM(total_qty)",
        "related_tables": ["quality_inspection"],
        "related_columns": ["defect_qty", "total_qty"],
        "business_domain": "供应链",
        "synonyms": ["质检不合格率", "不合格率", "次品率", "不良率"],
    },
    {
        "metric_name": "平均延期天数",
        "metric_definition": "生产/交付延期天数的平均值。",
        "formula": "AVG(delay_days)",
        "related_tables": ["production_delay"],
        "related_columns": ["delay_days"],
        "business_domain": "供应链",
        "synonyms": ["延期天数", "交付延期", "交期延误", "交付慢"],
    },
    {
        "metric_name": "库存周转天数",
        "metric_definition": "平均库存 / 日均销量，反映库存消化速度。",
        "formula": "AVG(inventory.quantity) / (SUM(sales_order.quantity) / 统计天数)",
        "related_tables": ["inventory", "sales_order"],
        "related_columns": ["quantity", "order_date"],
        "business_domain": "库存",
        "synonyms": ["库存周转", "周转天数", "周转慢", "滞销"],
    },
]


def get_table_metadata(table_name: str) -> dict | None:
    for t in TABLE_METADATA:
        if t["table_name"] == table_name:
            return t
    return None


def get_columns_of_table(table_name: str) -> list[dict]:
    return [c for c in COLUMN_METADATA if c["table_name"] == table_name]
