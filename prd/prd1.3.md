# 产品需求文档：AICO知识库同步与编排服务 - V1.3

## 1. 综述 (Overview)
### 1.1 项目背景与核心问题
随着业务扩展，系统需要为多个独立的业务场景（如“水务”、“公交”）向AICO平台同步知识库。为避免为每个场景重复开发，保证未来的可扩展性和可维护性，V1.3版本的核心目标是构建一个平台化的、可配置的、支持多场景（多租户）的知识库同步服务。该服务将作为系统内部正式知识库与外部AICO平台之间的数据桥梁，自动化地处理所有知识的增、删、改同步操作。

### 1.2 核心业务流程 / 用户旅程地图
V1.3是一个纯后端的、以配置驱动的服务，其核心流程分为两个层面：

*   **A. 管理员配置流程 (一次性)**:
    1.  管理员在系统后台，通过管理界面创建一个新的“同步场景”（如“公交知识库”）。
    2.  管理员在该场景下，填写所有与AICO平台对接所需的配置信息（如用户名、知识库名称等）。

*   **B. 系统自动执行流程 (周期性)**:
    1.  **扫描与分发**: 系统定时任务启动，扫描所有已启用的“同步场景”配置。
    2.  **数据准备**: 针对每个场景，从系统内部知识库中拉取对应的数据，并打包成文件。
    3.  **API编排**: 针对每个场景，使用其独立配置，自动化地、依次调用AICO平台的一系列API（认证、上传、切片、上线等）。
    4.  **状态同步**: 完成知识在AICO平台的“全量覆盖式”更新，统一实现知识的增、删、改。

## 2. 用户故事详述 (User Stories)

### 阶段一：平台化同步服务

---

#### **US-1.3.1: 作为系统管理员，我希望能通过后台配置来管理多个知识库的同步任务，以便于未来能快速、低成本地支持新业务场景。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 系统管理员
    *   **我希望** 系统能提供一个“场景配置”的管理功能，而不是将每个知识库的对接逻辑硬编码
    *   **以便于** 当需要接入新的知识库时，我只需在后台新增一条配置即可，无需后端工程师修改代码和重新部署服务。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **场景即配置 (Scenario as Configuration)**: 系统需引入“场景”概念，每个场景代表一个独立的知识库同步任务。
    2.  **核心配置字段**: 每个场景配置需包含：场景名称、场景编码、AICO平台对接所需的全部参数（用户名、用户ID、项目名、知识库名等）、任务调度规则（CRON表达式）、启用状态等。
    3.  **管理接口**: 系统需提供一套标准的CRUD API，用于对“场景配置”进行增、删、改、查。
    4.  **手动触发**: 除定时任务外，需提供一个API端点，允许管理员手动触发指定场景的同步任务，用于测试、补偿或即时更新。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功新增并启用一个场景**
        *   **GIVEN** 我作为管理员，登录系统后台
        *   **WHEN** 我通过界面填写了“燃气知识库”的所有AICO配置信息并保存启用
        *   **THEN** 系统`scenarios`表中应新增一条记录，并且在下一个调度周期，该场景的同步任务应被自动执行。

---

#### **US-1.3.2: 作为后台系统，我需要能够根据场景配置，自动将内部知识库全量同步至对应的AICO知识库，以便统一处理知识的增删改。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 后台系统
    *   **我希望** 执行一个配置驱动的、自动化的API调用编排流程
    *   **以便于** 将内部“事实源头”的知识库状态，以“全量覆盖”的模式，可靠地同步到外部AICO平台，从而原子性地完成所有知识的新增、修改和删除。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **任务调度**: 系统定时器会触发一个主任务，该任务从`scenarios`表中查询所有`is_active=1`的场景。
    2.  **任务分发**: 为每个查询到的场景，启动一个独立的、并行的同步工作流。
    3.  **数据准备**: 每个工作流根据其场景配置，从`knowledge_items`表中筛选出对应`scenario_id`的所有“已生效”的Q&A，并将其格式化为一个结构化文件（如CSV）。
    4.  **API编排 (Orchestration)**: 工作流严格按照AICO文档，依次执行以下API调用：
        *   获取`token`。
        *   获取`pid` (可缓存)。
        *   获取`kb_id` (可缓存)。
        *   **上传文件 (覆盖模式)**。
        *   轮询文件状态，直到上传成功。
        *   触发`split`（切片）。
        *   轮询文件状态，直到切片成功。
        *   触发`online`（上线）。
    5.  **日志与监控**: 整个编排过程中的每一步（API调用、成功、失败、重试）都必须有详细的日志记录。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 全量同步成功**
        *   **GIVEN** 内部“水务”知识库有{Q1, Q2'}两条知识，而AICO“水务”知识库有{Q1, Q2, Q3}
        *   **WHEN** “水务”场景的同步任务成功执行完毕
        *   **THEN** AICO平台上的“水务”知识库内容应被更新为{Q1, Q2'}，与内部系统状态完全一致。
---
*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: 纯后端服务，数据库
    *   **后端 (Backend)**:
        *   实现一个`ScenarioService`，提供对场景配置的CRUD操作。
        *   实现一个`AicoSyncOrchestrator`，负责执行单个场景的8步API调用编排逻辑。
        *   实现一个`MasterScheduler`，负责定时扫描场景并调用`AicoSyncOrchestrator`。
    *   **数据库 / 存储 (Database / Storage)**:
        *   **核心配置表**: `scenarios` (新增)。
        *   **核心数据源**: `knowledge_items` (需要增加`scenario_id`外键)。
*   **数据模型 / 接口契约 (Data Contracts & APIs)**:
    *   **`scenarios` 表结构**:
        ```sql
        CREATE TABLE `scenarios` (
          `id` int NOT NULL AUTO_INCREMENT,
          `scenario_code` varchar(50) NOT NULL,
          `scenario_name` varchar(100) NOT NULL,
          `is_active` tinyint(1) DEFAULT 1,
          `aico_username` varchar(100) NOT NULL,
          `aico_user_id` int NOT NULL,
          `aico_project_name` varchar(100) NOT NULL,
          `aico_kb_name` varchar(100) NOT NULL,
          `aico_cached_pid` int DEFAULT NULL,
          `aico_cached_kb_id` int DEFAULT NULL,
          `aico_cached_token` text DEFAULT NULL,
          `aico_token_expires_at` datetime DEFAULT NULL,
          `sync_schedule` varchar(50) DEFAULT '0 0 2 * * ?',
          PRIMARY KEY (`id`),
          UNIQUE KEY `uk_scenario_code` (`scenario_code`)
        ) COMMENT='多场景配置表';
        ```
    *   **场景管理API**:
        *   `POST /api/scenarios`
        *   `GET /api/scenarios`
        *   `PUT /api/scenarios/{id}`
        *   `POST /api/scenarios/{id}/trigger-sync`
*   **约束与边界 (Constraints & Boundaries)**:
    *   系统本身不存储AICO的原始文件，只在每次同步任务执行时，在内存中或临时文件中生成待上传的知识文件。
*   **非功能性需求 (Non-Functional)**:
    *   **可扩展性**: 系统的核心设计必须保证新增知识库场景时，无需进行代码级别的改动。
    *   **健壮性**: API调用编排流程需包含合理的重试机制和超时处理。任何一步失败，都应有明确的日志告警，并可被手动触发重跑。