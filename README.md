AI 跨境电商经营分析智能体DEMO
用户无需编写 SQL，用自然语言提问，Agent 自动完成：

```
自然语言问题 → SupervisorAgent（意图识别 + 任务分配 + HITL 审核）
   ├─ DataSubAgent：召回 → NL2SQL → 校验 → 执行 → 分析
   └─ SearchSubAgent：外部搜索 / 跨境平台搜索 / 详情抓取
→ 汇总合成 → SSE 流式输出 → 前端 ChatBI（报表 + Agent 执行轨迹）
```

支持四类意图：`INTERNAL_DATA` / `EXTERNAL_INFORMATION` / `MARKETPLACE_INTEL` / `HYBRID_ANALYSIS`。

> 定位不是聊天机器人、不是 RAG 问答、不是单纯 NL2SQL，而是 **「数据库驱动 + 外部工具增强」的企业经营分析 Agent**。

---

## 一、项目特点

- **保留纯数据库链路，新增外部工具能力**：在原「召回 → NL2SQL → 校验 → 执行 → 分析」链路之上，增加意图路由与 `external_web_search` 工具，实现内部数据与外部信息的交叉分析。
- **工具调用式 Agent 循环**：调用哪些工具由「规划器」决定（配置 `LLM_API_KEY` 时由大模型 function calling 自主决策，否则走确定性规则规划器回退）。工具内部逻辑固定，何时调用由智能体决定 —— 而非写死的线性管道。
- **零重依赖、离线可跑**：内置 SQLite 演示数仓 + 模拟公开信息知识库，无需 MySQL/Qdrant/ES/Docker 即可运行。
- **SQL 安全**：默认只允许 `SELECT`，从连接层（只读）与校验层双重拦截 DDL/DML。
- **可审计执行轨迹**：SSE 实时输出每一步，绝不暴露 LLM 隐藏思维链。
- **内部/外部数据严格区分**：最终答案明确分区「企业内部数据 / 外部公开信息 / 综合判断」，推测一律标记。

---

## 二、总体架构（多 Agent + Human-in-the-Loop）

```
                用户
                 ↓
          ChatBI Frontend（单文件 HTML + ECharts）
                 ↓
          FastAPI Backend（POST /api/query, SSE）
                 ↓
          Orchestrator（run() async generator + HITL resume）
                 ↓
       SupervisorAgent（主管 StateGraph + MemorySaver）
          │  route_intent → plan_tasks → hitl_review
          │      （意图识别 + 任务分配 + 人工审核）
          ├──────────────┬─────────────────────────────┐
          ↓              ↓                             ↓
   DataSubAgent    SearchSubAgent                build_answer
   （数据库链路）   （搜索链路）                  （结果汇总）
   召回→NL2SQL     外部搜索/跨境平台/详情
   →校验→执行→分析                                    ↓
          │                                  SSE Stream → UI
          └─────────── 三区分区答案 ←────────────┘
```

**架构要点**：

- **1 主管 + 2 子 Agent**：`SupervisorAgent` 负责意图识别、任务分配、HITL 决策与结果汇总；`DataSubAgent` 只做数据库链路（召回 → NL2SQL → 校验 → 执行 → 分析）；`SearchSubAgent` 只做搜索链路（外部搜索 / 跨境平台搜索 / 详情抓取）。三个 Agent 各自独立 StateGraph，分别位于 `supervisor/`、`data_agent/`、`search_agent/`。
- **Human-in-the-Loop**：主管在派发子 Agent 前评估风险，`HITL_MODE=manual` 时对高风险操作（执行 SQL / 跨境平台搜索 / 敏感经营数据）调用 `interrupt()` 暂停，等待人工确认后经 `Command(resume)` 继续；`auto`（默认）自动放行。
- **动态决策**：主管用条件边按 `tool_names` 派发子 Agent；`HYBRID_ANALYSIS` 场景先跑 DataSubAgent，再用其内部上下文聚焦 SearchSubAgent 检索词。
- **三路召回可插拔后端**：字段/指标召回默认走 Qdrant 向量检索、字段取值走 ES 全文检索；基础设施不可用时自动回退到 `scoring.py` 关键词打分。
- **规划器（Planner）**：LLM 自主决策（function calling）失败回退规则规划器；链式调用（marketplace 搜索后抓详情）由节点硬编码——保证关键步骤不依赖 LLM 决定。

---

## 三、目录结构

```
yiyi-agent/
├── run.py                      # 启动入口：python run.py
├── requirements.txt
├── backend/
│   ├── main.py                 # FastAPI 应用 + 静态托管 + lifespan
│   ├── config.py               # 配置（DB 路径 / LLM / 基础设施连接 / 召回后端）
│   ├── audit.py                # 审计日志（JSON Lines）
│   ├── agent/
│   │   ├── orchestrator.py     # 顶层编排入口：run() async generator + HITL resume + SSE 适配
│   │   ├── supervisor/         # 主管 Agent
│   │   │   ├── graph.py        # Supervisor StateGraph（路由 + 分配 + HITL + 汇总）
│   │   │   ├── state.py        # SupervisorState
│   │   │   ├── router.py       # 意图路由（INTERNAL/EXTERNAL/HYBRID/MARKETPLACE）
│   │   │   ├── planner.py      # 任务分配规划器（LLMPlanner / RulePlanner）
│   │   │   └── hitl.py         # Human-in-the-Loop 节点（interrupt 人工审核）
│   │   ├── data_agent/         # 数据库子 Agent（DataSubAgent）
│   │   │   ├── graph.py        # DataSubAgent StateGraph（召回→NL2SQL→校验→执行→分析）
│   │   │   ├── state.py        # DataAgentState
│   │   │   ├── nl2sql.py       # NL2SQL 引擎（规则 + LLM 扩展点）
│   │   │   ├── analyzer.py     # Result Analyzer + 异常检测 + 图表配置
│   │   │   ├── context.py      # DataAgentContext（LangGraph Runtime 上下文定义）
│   │   │   ├── recall_backend.py   # 召回后端选择 + 向量召回实现（Qdrant/ES）
│   │   │   └── nodes/          # 数据链路细粒度节点（9 个）
│   │   ├── search_agent/       # 搜索子 Agent（SearchSubAgent）
│   │   │   ├── graph.py        # SearchSubAgent StateGraph
│   │   │   ├── state.py        # SearchAgentState
│   │   │   └── nodes/          # external_search / marketplace_search / fetch_details
│   │   └── shared/             # 三 Agent 共享
│   │       ├── answer.py       # 最终答案合成（内/外/综合三分区）
│   │       ├── run_logger.py   # 终端运行日志 + Token 计量
│   │       └── sse.py          # SSE 事件构造
│   ├── tools/
│   │   ├── registry.py              # 工具注册表（8 工具 + LLM schema）
│   │   ├── table_recall.py          # 表召回（scoring 兜底）
│   │   ├── schema_recall.py         # 字段召回（scoring 兜底）
│   │   ├── metric_recall.py         # 指标召回（scoring 兜底）
│   │   ├── sql_execute.py           # SQL 执行（内含安全校验）
│   │   ├── external_web_search.py   # 外部信息搜索
│   │   ├── aliyun_marketplace_search.py  # 阿里云 OpenSearch 商品搜索
│   │   └── fetch_product_detail.py  # 商品详情抓取
│   ├── conf/                   # 结构化配置（对齐 shopkeeper-agent）
│   │   ├── app_config.py       # DBConfig/Qdrant/Embedding/ES/LLM/Logging
│   │   └── meta_config.py      # Table/Column/Metric 同步配置
│   ├── clients/                # 客户端管理器（惰性 init + 失败降级）
│   │   ├── mysql_client_manager.py     # meta + dw 两套 MySQL
│   │   ├── qdrant_client_manager.py
│   │   ├── es_client_manager.py
│   │   └── embedding_client_manager.py # TEI / bge-large-zh-v1.5
│   ├── entities/               # 业务实体（dataclass）
│   │   └── table_info / column_info / metric_info / value_info / column_metric
│   ├── models/                 # SQLAlchemy ORM（base + 4 张元数据表）
│   ├── repositories/           # 仓储层
│   │   ├── mysql/meta/ + mappers/    # 元数据落库
│   │   ├── mysql/dw/                 # 数仓真实结构/样例值查询
│   │   ├── qdrant/                   # 字段/指标向量仓储
│   │   └── es/                       # 字段取值全文索引仓储
│   ├── services/
│   │   └── meta_knowledge_service.py # 元数据知识构建（Meta→Qdrant→ES）
│   ├── scripts/
│   │   └── build_meta_knowledge.py   # 同步脚本入口
│   ├── prompt/                 # 关键词扩展提示词模板
│   ├── core/                   # 日志 + 请求上下文
│   ├── api/                    # chat / sse / lifespan
│   ├── database/
│   │   ├── metadata.py         # 表/字段/指标元数据字典（离线兜底）
│   │   ├── schema.py           # 建表 SQL
│   │   ├── seed.py             # 模拟数据生成（含市场叙事）
│   │   └── connection.py       # SQLite 只读连接
│   ├── security/
│   │   └── sql_validator.py    # SQL 安全校验（仅 SELECT）
│   └── static/
│       └── index.html          # ChatBI 前端
├── conf/                       # YAML 配置（app_config.yaml / meta_config.yaml）
├── docker/                     # docker-compose + MySQL/Qdrant/ES/Embedding
├── data/                       # 运行时生成 yiyi.db / audit.log
└── tests/
    └── test_cases.py           # 6 个验收案例
```

---

## 四、演示数据（8 张表）

使用固定随机种子生成 2024-01 ~ 2025-12 的跨境经营数据，刻意埋入叙事线索：

| 表 | 说明 | 规模 |
| --- | --- | --- |
| `sales_order` | 销售订单事实表（时间/客户/店铺/商品/国家/平台/数量/金额） | ~1600 行 |
| `product` | 商品 SKU 主数据（品类/成本/售价） | 30 |
| `store` | 店铺主数据（TikTok Shop 10 家矩阵 + Amazon/独立站/Shein） | 17 |
| `customer` | B端/C端客户主数据 | 150 |
| `inventory` | 库存 + 安全库存 | 30 |
| `quality_inspection` | 质检批次（不合格率） | 180 |
| `production_delay` | 生产延期记录 | 70 |

**埋入的市场叙事**（支撑混合分析案例）：

- 美国市场 2025 下半年销量下滑，8/10 月出现明显环比骤降；
- TikTok Shop 平台 2025 年份额持续走高；
- 中东市场 2025 年高速增长；
- 4 个热销 SKU 库存偏低，15 天内可能缺货。

---

## 五、快速开始

```bash
cd yiyi-agent
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

打开浏览器访问 `http://127.0.0.1:8000` 即可使用前端。

> 首次启动会自动创建 `data/yiyi.db` 并灌入模拟数据（幂等，已存在则跳过）。

**实时观察终端日志**：

服务把每次问数都打成结构化 kv 日志输出到 stdout。日志格式：

```
[2026-09-09 11:40:29] [yiyi-agent] [req=c2b733cf] [INFO] request_received query_len=16
[2026-09-09 11:40:29] [yiyi-agent] [req=c2b733cf] [TOOL] call sql_execute tool="sql_execute" row_count=12 duration_ms=1
[2026-09-09 11:40:29] [yiyi-agent] [req=c2b733cf] [DONE] OK intent="INTERNAL_DATA" tools="table_recall,..." sql_len=191 external_count=0 prompt_tokens=1042 completion_tokens=93 total_tokens=1135 duration_ms=2592
```

每行都带 8 位 `req_id`，可通过 `grep [req=c2b733cf]` 还原整次请求；DONE 行汇总 token 用量与耗时。

后台运行时把日志写文件：

```bash
cd /d/myself/yiyi-agent && ./.venv/Scripts/python.exe run.py > data/server.log 2>&1 &
# 实时观察
tail -f data/server.log
```

运行验收测试：

```bash
python tests/test_cases.py
```

---

## 六、元数据基础设施（可选：MySQL + Qdrant + ES + Embedding）

默认离线模式无需任何外部服务。如需对齐 shopkeeper-agent 的「元数据库 + 向量库 + 全文索引」架构，可按以下步骤启用：

```bash
# 1. 启动基础服务（MySQL 8 + Qdrant + ES + Kibana + TEI Embedding）
cd yiyi-agent
docker compose -f docker/docker-compose.yaml up -d

# 2. 安装完整依赖（离线演示可跳过）
pip install -r requirements.txt

# 3. 同步元数据：从 dw 读表结构/示例值 → 写 meta MySQL + Qdrant 向量 + ES 全文索引
python -m backend.scripts.build_meta_knowledge -c conf/meta_config.yaml

# 4. 启动服务（lifespan 会自动初始化并探测向量后端）
python run.py
```

**分层说明**：

| 层 | 技术 | 作用 |
| --- | --- | --- |
| 元数据库 | MySQL（`meta` 库） | `table_info` / `column_info` / `metric_info` / `column_metric` 四张表，结构化元数据 |
| 数仓 | MySQL（`dw` 库）或 SQLite | 真实表结构、字段类型、示例值来源 |
| 向量库 | Qdrant（两个 collection） | 字段语义向量、指标语义向量 |
| 全文索引 | Elasticsearch（IK 分词） | 字段真实取值（国家/平台/品类/仓库等） |
| Embedding | TEI（`BAAI/bge-large-zh-v1.5`） | 关键词 → 1024 维向量 |

**自动回退**：`VECTOR_RECALL_BACKEND=auto`（默认）时，lifespan 启动会探测 Qdrant/ES/Embedding 是否可达；不可达（或未安装对应依赖）时，召回链路自动回退到 `scoring.py` 关键词打分，服务不报错。`off` 强制关键词打分（完全离线），`on` 强制向量召回。

---

## 七、接口

| 接口 | 方法 | 说明 |
| --- | --- | --- |
| `/api/query` | POST | 提交问题，SSE 流式返回执行轨迹与最终答案 |
| `/api/query/confirm` | POST | HITL 人工审核确认（`thread_id` + `decision`：approve/reject） |
| `/api/health` | GET | 健康检查 |
| `/api/samples` | GET | 推荐样例问题 |
| `/` | GET | ChatBI 前端 |

SSE 事件类型：`received` / `intent_detected` / `plan_ready` / `hitl_review` / `hitl_pending` /
`keywords_extracted` / `table_recall` / `schema_recall` / `value_recall` / `metric_recall` / `retrieval_merged` /
`sql_generated` / `sql_validated` / `sql_executing` / `sql_completed` / `anomaly_detected` /
`external_tool_required` / `external_tool_calling` / `external_tool_completed` /
`result_analysis` / `answer_generated` / `error`。

### Human-in-the-Loop 使用说明

`HITL_MODE=manual` 时，高风险操作（执行 SQL / 跨境平台搜索 / 涉及库存、成本、利润等敏感数据）会触发中断：

1. 前端收到 `hitl_pending` 事件（含 `thread_id` 与审核理由）；
2. 用户确认后调用 `POST /api/query/confirm`，body：`{"thread_id": "...", "decision": "approve"}`（或 `reject`）；
3. `approve` 继续执行，`reject` 中止并返回 error。

默认 `HITL_MODE=auto`，高风险操作自动放行，方便离线演示。

---

## 七、6 个最终验收案例

| # | 问题 | 预期链路 |
| --- | --- | --- |
| 1 | 2025年各月销量变化趋势如何？ | 内部链路 + 折线图，**不调用**外部工具 |
| 2 | 2025年美国内衣市场有什么趋势？ | 仅外部搜索，**不查询**企业数据库 |
| 3 | 为什么我们2025年美国市场销量下降？ | 数据库 + 外部搜索 + 综合判断（区分内/外/推测） |
| 4 | TikTok Shop最近有什么规则变化，会不会影响我们的销量？ | 外部搜索（优先官方）+ 内部销量 |
| 5 | 哪个SKU未来15天可能缺货？ | 仅内部数据（库存 + 近30天销量），**不擅自**调用外部工具 |
| 6 | 搜索亚马逊/temu/eBay的情趣内衣热销榜的链接 | 阿里云 OpenSearch 搜索 + 链式抓取详情（尺码/价格/月销/评论） |

更多示例：`亚马逊和eBay情趣内衣有哪些？要看价格和月销` `我们Temu上卖的蕾丝套装和亚马逊热销款相比怎么样？`
`哪个平台销售额最高？` `今年B端客户复购率是多少？` `哪些产品质检不合格率最高？` 等。

---

## 八、接入真实 LLM 与真实搜索

- **真实 LLM 规划器**：复制 `.env.example` 为 `.env`，填入 `LLM_API_KEY`（OpenAI 兼容接口）。
  配置后 `LLMPlanner` 用 function calling 自主决定调用哪些工具；失败自动回退规则规划器。
- **真实外部信息搜索**：在 `backend/tools/external_web_search.py` 中实现 `_real_search()`，
  并把 `EXTERNAL_SEARCH_BACKEND` 设为 `real`。
- **真实阿里云 OpenSearch 商品搜索**（用于 Amazon / Temu / eBay 调研）：
  1. 阿里云控制台 → 开放搜索 OpenSearch → 创建「文档搜索」类型应用；
  2. 把 Amazon / Temu / eBay 的商品文档（字段含 `url / title / platform / tags` 等）灌入该应用；
  3. 在 `.env` 设置：`ALIYUN_ACCESS_KEY_ID` / `ALIYUN_ACCESS_KEY_SECRET` /
     `ALIYUN_OPENSEARCH_ENDPOINT`（如 `https://opensearch-cn-hangzhou.aliyuncs.com`）/
     `ALIYUN_OPENSEARCH_APP`（应用名）；
  4. 把 `MARKETPLACE_SEARCH_BACKEND` 设为 `aliyun_opensearch`；
  5. 真实调用失败时会自动回退到 mock，保证链路不中断。
- **真实商品详情抓取**：在 `.env` 设置 `SCRAPER_API_KEY` 与 `PRODUCT_FETCH_BACKEND=scraperapi`，
  通过 ScraperAPI 代理绕过 Amazon / Temu / eBay 的反爬。也可对接 Bright Data、阿里云 ScrapingHub 等同类服务。
  `PRODUCT_FETCH_BACKEND=direct` 表示直连（仅对受信任小站点有效）。

详细配置项见 `.env.example`。


---

## 九、重要设计原则

1. 企业数据库是经营数据的唯一权威来源；外部工具只提供公开信息，不替代数据库。
2. `INTERNAL_DATA` 不调用外部工具；`EXTERNAL_INFORMATION` 不强制查库；`HYBRID` 两者都要。
3. Table/Schema/Metric Recall 必须保留，NL2SQL 必须基于召回结果，指标不能靠猜。
4. SQL 必须过安全校验，默认只允许 `SELECT`。
5. SSE 实时输出可审计轨迹，不暴露隐藏思维链；内部/外部数据明确分区；推测不写成事实。

---

## 十一、说明

本项目为自包含的完整可运行实现，用于落地「跨境电商经营分析智能体」的架构与流程验证。
外部公开信息为**模拟数据**（示意性公开信源），用于演示交叉分析能力，不代表真实市场数据。

`aliyun_marketplace_search` 工具的 mock 后端内置了 13 条 Amazon / Temu / eBay 的情趣内衣
热销商品，覆盖蕾丝套装 / 大码 / COS 角色 / 缎面睡裙等典型品类。`fetch_product_detail` 从本地商品库
反查对应字段，生产环境建议配置 `SCRAPER_API_KEY` 接入真实抓取。
