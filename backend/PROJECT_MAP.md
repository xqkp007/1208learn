# Backend 项目目录地图

## 项目概览

基于 FastAPI 的对话数据 ETL 服务，支持从 MySQL 源库抽取对话数据到目标库，并提供 FAQ 提取、知识库管理、分类审核等业务功能。

## 作用范围

本次扫描目录：`backend/`

## 入口与运行链路

### 应用启动
- **入口文件**：`backend/app/main.py`
- **启动命令**：`uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`

### 运行链路

```
main.py (FastAPI 应用)
    ├─ lifespan 生命周期管理
    │   ├─ 启动: SchedulerManager.start()
    │   └─ 关闭: SchedulerManager.shutdown()
    │
    ├─ 路由注册 (按版本号组织)
    │   ├─ /api/v1 - ETL 触发 (etl_routes)
    │   ├─ /api/v1_2 - FAQ 管理 (faq_routes)
    │   ├─ /api/v1_3 - 场景管理 (scenario_routes)
    │   ├─ /api/v1_4 - 审核管理 (review_routes)
    │   ├─ /api/v1_4_1 - 知识库管理 (knowledge_routes)
    │   ├─ /api/v1_6 - 认证授权 (auth_routes)
    │   ├─ /api/v1_8 - 批量审核 (bulk_routes)
    │   ├─ /api/v1_10 - 管理员接口 (admin_routes)
    │   ├─ /api/v1_12 - 分类知识库 (kb_taxonomy_routes)
    │   └─ /api/v1_14 - 分类审核工作台 (kb_taxonomy_review_routes)
    │
    └─ 中间件
        └─ CORSMiddleware (允许 localhost:5176)
```

### 定时任务链路

```
SchedulerManager (APScheduler)
    ├─ daily_dialog_etl (默认每天 01:00)
    │   └─ DialogETLService.run_for_date()
    │       └─ 从 source_db 读取 people_customer_dialog
    │           └─ 写入 target_db 的 prepared_conversations
    │
    ├─ daily_faq_extraction (默认每天 03:00)
    │   └─ FAQExtractionService.run()
    │       └─ 从 prepared_conversations 提取 FAQ
    │
    └─ CompareKbSyncService.run()
        └─ 同步知识库对比数据
```

## 关键配置与存储键

### 环境变量配置（项目根目录 `.env`）

#### 数据库配置（必需）
- `URL` / `DATABASE_URL` - JDBC 风格的 MySQL 连接串
- `username` / `DATABASE_USERNAME` - 数据库用户名
- `password` / `DATABASE_PASSWORD` - 数据库密码

#### 源/目标库分离（可选）
- `SRC_DB_HOST`, `SRC_DB_NAME` - 源库配置
- `DST_DB_HOST`, `DST_DB_NAME` - 目标库配置

#### AICO 双环境切换（可选）
- `AICO_HOST` - 当前 AICO 服务地址
- `AICO_HOST_TEST` - 测试环境地址
- `AICO_HOST_PROD` - 生产环境地址
- `TEST_URL`, `TEST_USERNAME`, `TEST_PASSWORD` - 测试环境 DB
- `PROD_URL`, `PROD_USERNAME`, `PROD_PASSWORD` - 生产环境 DB

#### 调度与性能（可选）
- `ETL_CRON` - ETL 定时表达式（默认 `0 1 * * *`）
- `FAQ_CRON` - FAQ 提取定时表达式（默认 `0 3 * * *`）
- `ETL_MAX_WORKERS` - ETL 并发 worker 数（默认 4）
- `FAQ_MAX_WORKERS` - FAQ 提取并发数（默认 5）
- `APP_TIMEZONE` - 应用时区（默认 `Asia/Shanghai`）
- `LOG_LEVEL` - 日志级别（默认 `INFO`）

#### AICO 集成（可选）
- `AICO_USER_PORT`, `AICO_PROJECT_PORT`, `AICO_KB_PORT`
- `AICO_TIMEOUT` - 超时时间（秒，默认 10）
- `AICO_FILE_DELETE_ENDPOINT`, `AICO_FILE_DELETE_PATH_TEMPLATE`
- `AICO_CHATBOT_URL`, `AICO_CHATBOT_API_KEY`
- `AICO_AUTO_REVIEW_URL`, `AICO_COMPARE_REVIEW_URL`

#### 认证（可选）
- `AUTH_SECRET_KEY` - JWT 签名密钥
- `AUTH_ALGORITHM` - JWT 算法（默认 `HS256`）
- `AUTH_ACCESS_TOKEN_EXPIRES_MINUTES` - Token 过期时间（默认 10080 分钟）

### 数据库表

#### 源库表
- `people_customer_dialog` - 对话数据源表

#### 目标库表
- `prepared_conversations` - ETL 转换后的对话表
- `scenarios` - 场景配置表（包含 AICO 集成信息）
- `faqs` - FAQ 知识库表
- `knowledge` - 知识库条目表
- `kb_taxonomy` - 三级分类表（v1.12）
- `kb_taxonomy_review` - 分类审核记录表（v1.14）

## 目录与文件说明

```
backend/
├── app/                          # 应用主目录
│   ├── api/                      # API 路由（按版本组织）
│   │   ├── v1/                   # v1.0 - ETL 触发
│   │   │   └── routes.py         # ETL 手动触发接口
│   │   ├── v1_2/                 # v1.2 - FAQ 管理
│   │   │   └── faq_routes.py     # FAQ 增删改查
│   │   ├── v1_3/                 # v1.3 - 场景管理
│   │   │   └── scenario_routes.py # 场景配置 CRUD
│   │   ├── v1_4/                 # v1.4 - 审核管理
│   │   │   └── review_routes.py  # 对话审核接口
│   │   ├── v1_4_1/               # v1.4.1 - 知识库管理
│   │   │   └── knowledge_routes.py # 知识库条目管理
│   │   ├── v1_6/                 # v1.6 - 认证授权
│   │   │   └── auth_routes.py    # 登录/Token 验证
│   │   ├── v1_8/                 # v1.8 - 批量审核
│   │   │   └── bulk_routes.py    # 批量审核接口
│   │   ├── v1_10/                # v1.10 - 管理员接口
│   │   │   └── admin_routes.py   # 管理员专用接口
│   │   ├── v1_12/                # v1.12 - 分类知识库
│   │   │   └── kb_taxonomy_routes.py # 三级分类管理
│   │   └── v1_14/                # v1.14 - 分类审核工作台
│   │       └── kb_taxonomy_review_routes.py # 分类审核接口
│   │
│   ├── core/                     # 核心模块
│   │   ├── db.py                 # 数据库连接配置
│   │   │   └─ SOURCE_ENGINE / TARGET_ENGINE 双引擎
│   │   ├── settings.py          # 配置加载与环境变量解析
│   │   │   └─ 支持 AICO 双环境自动切换
│   │   ├── logging.py            # 日志配置
│   │   └── security.py           # 安全工具（JWT 等）
│   │
│   ├── jobs/                     # 后台任务
│   │   └── scheduler.py          # APScheduler 调度器
│   │       ├─ daily_dialog_etl (每日对话 ETL)
│   │       ├─ daily_faq_extraction (每日 FAQ 提取)
│   │       └─ CompareKbSyncService (知识库对比同步)
│   │
│   ├── models/                   # SQLAlchemy 数据模型
│   │   ├── base.py               # 模型基类
│   │   ├── dialog.py             # 对话模型
│   │   ├── faq_review.py         # FAQ 审核模型
│   │   ├── kb_taxonomy.py        # 三级分类模型
│   │   ├── kb_taxonomy_review.py # 分类审核模型
│   │   ├── knowledge.py          # 知识库条目模型
│   │   ├── scenario.py           # 场景模型
│   │   └── user.py               # 用户模型
│   │
│   ├── schemas/                  # Pydantic 请求/响应模型
│   │   ├── auth.py               # 认证相关 Schema
│   │   ├── etl.py                # ETL 相关 Schema
│   │   ├── faq.py                # FAQ Schema
│   │   ├── kb_taxonomy.py        # 三级分类 Schema
│   │   ├── kb_taxonomy_review.py # 分类审核 Schema
│   │   ├── knowledge.py          # 知识库条目 Schema
│   │   ├── review.py             # 审核相关 Schema
│   │   └── scenario.py           # 场景 Schema
│   │
│   ├── services/                 # 业务逻辑层
│   │   ├── aico_sync.py          # AICO 知识库同步服务
│   │   ├── auth.py               # 认证服务
│   │   ├── compare_kb_sync.py    # 知识库对比同步服务
│   │   ├── dialog_etl.py         # 对话 ETL 服务
│   │   ├── faq_extraction.py     # FAQ 提取服务
│   │   ├── kb_taxonomy.py        # 三级分类服务
│   │   ├── kb_taxonomy_review.py # 分类审核服务
│   │   ├── knowledge.py          # 知识库条目服务
│   │   ├── review.py             # 审核服务
│   │   └── scenario.py           # 场景服务
│   │
│   ├── main.py                   # FastAPI 应用入口
│   └── __init__.py
│
├── sql/                          # 数据库初始化脚本
│   ├── kb_taxonomy_v1_12.sql             # v1.12 三级分类表结构
│   ├── kb_taxonomy_review_v1_14.sql      # v1.14 分类审核表结构
│   └── kb_taxonomy_review_seed_v1_14.sql # 分类审核测试数据
│
├── tests/                        # 测试目录
│   └── test_auto_review.py       # 自动审核测试
│
├── .venv/                        # Python 虚拟环境（忽略）
├── README.md                     # 项目说明文档
├── requirements.txt              # Python 依赖
└── test_knowledge.csv            # 测试用知识库数据
```

## 关键模块关系/调用链

### ETL 数据流

```
DialogETLService
    ├─ 读取: source_db.people_customer_dialog (按 group_code 分组)
    ├─ 转换: 映射字段到 prepared_conversations 模型
    └─ 写入: target_db.prepared_conversations (幂等性检查 call_id)
```

### FAQ 提取流程

```
FAQExtractionService
    ├─ 扫描: prepared_conversations 表
    ├─ 提取: 基于对话内容生成候选 FAQ
    ├─ 过滤: 去重、质量评分
    └─ 写入: faqs 表
```

### 知识库同步流程

```
AicoSyncService
    ├─ 读取: scenarios 表获取 AICO 配置
    ├─ 推送: 知识库条目到 AICO 平台
    └─ 回调: 处理 AICO 返回结果
```

### 分类审核流程（v1.14）

```
KbTaxonomyReviewService
    ├─ 读取: kb_taxonomy 表的三级分类
    ├─ 导入: CSV/XLSX 文件（业务域/一级/二级/三级/定义）
    ├─ 审核: 人工审核分类定义
    └─ 写入: kb_taxonomy_review 表
```

## 风险/遗留/不确定点

### 假设/未确认
1. **AICO 集成** - `app/services/aico_sync.py` 未读取，假设通过 httpx 调用 AICO API
2. **数据库表结构** - 部分表结构未在代码中定义（如 `people_customer_dialog`），假设已在数据库中存在
3. **测试覆盖** - `tests/` 目录仅有一个测试文件，不确定测试完整性

### 可能遗留
1. `test_knowledge.csv` - 可能是测试遗留数据，未确认是否仍在使用
2. `.DS_Store` 文件 - macOS 系统文件，应加入 `.gitignore`

### 风险点
1. **环境变量解析** - `settings.py` 中支持非标准 `key: value` 格式，可能导致配置解析不一致
2. **并发控制** - ETL 使用 `ETL_MAX_WORKERS` 控制并发，需确保数据库连接池配置充足
3. **幂等性保证** - ETL 服务通过检查 `call_id` 保证幂等性，但未确认是否有唯一索引约束
4. **AICO 依赖** - 服务高度依赖 AICO 平台可用性，需考虑降级策略

## 本次更新

- **日期**：2025-01-26
- **范围**：`backend/` 目录
- **变更点**：首次生成 PROJECT_MAP.md 文档
