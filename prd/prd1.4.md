# 产品需求文档：人工审核后台服务 - V1.4

## 1. 综述 (Overview)
### 1.1 项目背景与核心问题
在V1.1版本设计了“统一审核工作台”的前端交互界面后，需要一个稳定可靠的后台服务为其提供数据支撑和业务逻辑处理。V1.4版本的核心目标是开发一套专门服务于审核工作台的API，打通从“待审核FAQ”到“正式知识库”的数据流转路径。该版本是连接AI自动提取（上游）和知识库同步（下游）的关键人工环节，为整个系统的“人工质检”能力提供核心后台动力。

### 1.2 核心业务流程 / 用户旅程地图
V1.4版本是一个纯后台API服务，它支撑的前端用户旅程如下：
1.  **加载数据**: 审核员打开“统一审核工作台”页面，前端调用API拉取待审核FAQ列表。
2.  **审核决策**: 审核员在界面上进行操作（直接采纳、展开编辑后采纳、废弃）。
3.  **提交变更**: 前端将用户的决策通过对应的API提交给后台。
4.  **后台处理**: 后台服务接收到请求，对`pending_faqs`（待审核表）和`knowledge_items`（正式知识库表）进行相应的读写操作，完成数据的状态流转。

## 2. 用户故事详述 (User Stories)

### 阶段一：审核工作台API

---

#### **US-1.4: 作为前端开发者，我需要一套清晰的API来支撑审核工作台的所有功能，以便我能实现数据的展示、提交和更新。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 前端开发者
    *   **我希望** 能调用一组定义明确、功能专注的RESTful API
    *   **以便于** 我能快速实现V1.1版本“统一审核工作台”界面的所有交互功能，包括获取待办列表、采纳新知识和废弃无效建议。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **数据流转**: 本服务的核心数据流是从`pending_faqs`表到`knowledge_items`表。所有API操作都围绕这两张表进行。
    2.  **采纳逻辑**: “采纳”是一个写操作。它会将一条经过确认的Q&A数据写入到`knowledge_items`表，并更新源`pending_faqs`记录的状态为`processed`，以防止重复审核。
    3.  **废弃逻辑**: “废弃”是一个更新操作。它仅更新`pending_faqs`记录的状态为`discarded`，作为记录，但不会产生任何新的知识条目。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 完整审核流程**
        *   **GIVEN** `pending_faqs`表中有一条ID为101的待审核记录
        *   **WHEN** 前端先调用`GET /api/v1.4/pending-faqs`成功获取到该记录，然后用户编辑后调用`POST /api/v1.4/knowledge-items`提交采纳
        *   **THEN** `knowledge_items`表中应新增一条记录，同时`pending_faqs`表中ID为101的记录状态应变为`processed`。

---
*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: 纯后端服务，数据库
    *   **后端 (Backend)**:
        *   基于Java/Go/Python等语言的Web框架，实现三个核心API Controller。
        *   `ReviewService`: 封装核心业务逻辑，处理数据表的增删改查。
    *   **数据库 / 存储 (Database / Storage)**:
        *   **核心依赖表**: V1.4的实现强依赖于以下两张表的最终结构。
        *   **待审核FAQ表 (`pending_faqs`)**: 作为数据输入源。
        *   **正式知识库表 (`knowledge_items`)**: 作为数据输出目标。
*   **数据模型 / 接口契约 (Data Contracts & APIs)**:

    *   **核心表结构1: `pending_faqs`**
        ```sql
        CREATE TABLE `pending_faqs` (
          `id` bigint NOT NULL AUTO_INCREMENT,
          `question` text NOT NULL COMMENT 'AI提取的原始问题',
          `answer` text NOT NULL COMMENT 'AI提取的原始答案',
          `status` varchar(20) NOT NULL DEFAULT 'pending' COMMENT '状态: pending, processed, discarded',
          `source_group_code` varchar(2) DEFAULT NULL COMMENT '来源场景编码',
          `source_call_id` varchar(64) DEFAULT NULL COMMENT '来源对话的call_id',
          `source_conversation_text` longtext COMMENT '聚合后的原始对话全文',
          `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
          `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`)
        ) COMMENT='待审核的FAQ表';
        ```

    *   **核心表结构2: `knowledge_items`**
        ```sql
        CREATE TABLE `knowledge_items` (
          `id` bigint NOT NULL AUTO_INCREMENT COMMENT '唯一主键',
          `scenario_id` INT NOT NULL COMMENT '关联到scenarios表的ID，标识所属场景',
          `question` text NOT NULL COMMENT '审核通过后的标准问题',
          `answer` text NOT NULL COMMENT '审核通过后的标准答案',
          `status` varchar(20) NOT NULL DEFAULT 'active' COMMENT '状态: active (已生效), disabled (已禁用)',
          `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
          `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`),
          KEY `idx_scenario_id` (`scenario_id`)
        ) COMMENT='正式知识库表 (事实源头)';
        ```
    ---
    *   **API Endpoint 1: 获取待审核FAQ列表**
        *   **`GET /api/v1.4/pending-faqs`**
        *   **Query参数**:
            *   `page` (int, optional, default: 1): 页码。
            *   `pageSize` (int, optional, default: 20): 每页数量。
            *   `keyword` (string, optional): 在`question`字段中模糊搜索的关键词。
        *   **成功响应 (200 OK)**:
            ```json
            {
              "total": 150,
              "page": 1,
              "pageSize": 20,
              "items": [
                {
                  "id": 101,
                  "question": "如何查询水费？",
                  "answer": "您可以通过手机APP查询...",
                  "source_conversation_text": "客服：您好...市民：你好我想查水费..."
                }
              ]
            }
            ```

    *   **API Endpoint 2: 采纳FAQ并创建知识**
        *   **`POST /api/v1.4/knowledge-items`**
        *   **请求体**:
            ```json
            {
              "pendingFaqId": 101, // 必填, 来源的待审核记录ID
              "scenarioId": 1,     // 必填, 该知识所属的场景ID
              "question": "如何查询上个月的水费账单？", // 必填, 审核员最终确认或修改后的问题
              "answer": "您可以通过手机APP或官网，进入“我的账单”页面查看详情。" // 必填, 最终确认的答案
            }
            ```
        *   **成功响应 (201 Created)**:
            ```json
            {
              "id": 58, // 新创建的knowledge_item的ID
              "status": "active"
            }
            ```

    *   **API Endpoint 3: 废弃待审核FAQ**
        *   **`DELETE /api/v1.4/pending-faqs/{id}`**
        *   **路径参数**: `id` (long): 要废弃的待审核记录ID。
        *   **成功响应 (200 OK)**:
            ```json
            {
              "message": "Pending FAQ with id 102 has been discarded."
            }
            ```
*   **约束与边界 (Constraints & Boundaries)**:
    *   本版本**不包含**对`knowledge_items`表的“读取(GET)”和“更新(PUT)”接口，这些将与AICO对接功能一起在后续版本中实现。
*   **非功能性需求 (Non-Functional)**:
    *   所有API的P95响应时间应低于200ms。
    *   API需要提供基础的认证和授权机制，确保只有授权用户（审核员）才能调用。