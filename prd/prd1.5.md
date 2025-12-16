# 产品需求文档：AI自动化提取服务 (极简版) - V1.5

## 1. 綜述 (Overview)
### 1.1 项目背景与核心问题
V1.2版本已实现对话数据的预处理与聚合，形成了待AI处理的`prepared_conversations`表。V1.4版本则为人工审核环节提供了API支持。V1.5版本的核心目标是构建一个自动化的AI处理引擎，将这两个环节连接起来。该服务将通过调用一个预先配置好的、固定的AICO智能体，对已聚合的对话文本进行FAQ提取，并将提取结果存入待审核列表（`pending_faqs`表），从而实现从原始对话到待审Q&A的端到端自动化。

### 1.2 核心业务流程 / 用户旅程地图
V1.5是一个纯后端的、自动化的定时脚本任务，其核心流程如下：
1.  **阶段一：定时触发** - 系统在每日指定时间自动启动AI提取任务。
2.  **阶段二：并发处理** - 任务从`prepared_conversations`表中拉取待处理的对话，以固定的并发数（5个并发）调用单一的、预设的AICO智能体API。
3.  **阶段三：解析与入库** - 服务解析AICO返回的文本结果（“问题/答案”对 或 “否”），并将成功提取的Q&A存入`pending_faqs`表，等待人工审核。

## 2. 用户故事详述 (User Stories)

### 阶段一：自动化AI提取脚本

---

#### **US-1.5: 作为后台系统，我需要通过一个带并发控制的定时脚本，自动调用固定的AICO智能体来处理对话，以便完成FAQ的自动化提取。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 后台系统
    *   **我希望** 能够通过一个简单、高效的定时脚本，自动化地完成每日的AI分析与FAQ提取工作
    *   **以便于** 用最小的开发成本和配置复杂度，快速打通从“已准备好的对话”到“待审核FAQ”的数据流转。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **定时触发**:
        *   系统需配置一个定时任务，在每日固定时间（如凌晨03:00）自动执行。
    2.  **数据捞取**:
        *   任务启动后，从`prepared_conversations`表中查询`status`为`unprocessed`的记录。
    3.  **并发API调用**:
        *   系统必须以**5个并发**的固定并发度，并行处理捞取到的对话记录。
        *   对于每一条对话，系统执行以下操作：
            1.  从应用的配置文件中读取**固定**的AICO智能体URL和API Key。
            2.  将`prepared_conversations`表中的`full_text`字段作为`query`参数的值。
            3.  构建请求体`{"query": full_text, "stream": false}`。
            4.  向固定的AICO API Endpoint发起`POST`请求。
    4.  **响应解析逻辑**:
        *   从AICO返回的JSON中，提取`data.text[0]`的字符串值。
        *   **情况一 (提取失败)**: 如果该字符串经`trim()`处理后等于`"否"`，则视为本次无有效产出。
        *   **情况二 (提取成功)**: 如果字符串不是`"否"`，则通过字符串分割，以“问题：”和“答案：”为分隔符，提取出Q&A内容。
    5.  **数据入库与状态更新**:
        *   对于**情况一**，更新`prepared_conversations`表中对应记录的`status`为`processed_no_faq`。
        *   对于**情况二**，将提取的Q&A写入`pending_faqs`表，并更新`prepared_conversations`中对应记录的`status`为`completed`。
    6.  **错误处理**: API调用失败（网络超时、业务错误码等）后，应进行有限次数的重试。最终失败的，需更新`prepared_conversations`记录状态为`failed`并记录详细错误日志。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 成功提取**
        *   **GIVEN** `prepared_conversations`中有一条待处理对话，AICO返回“问题：A 答案：B”
        *   **WHEN** 定时任务执行
        *   **THEN** `pending_faqs`表中应新增一条Q为A、A为B的记录，且原记录状态更新为`completed`。
    *   **场景2: AI返回"否"**
        *   **GIVEN** `prepared_conversations`中有一条待处理对话，AICO返回“否”
        *   **WHEN** 定时任务执行
        *   **THEN** `pending_faqs`表无新增记录，且原记录状态更新为`processed_no_faq`。
    *   **场景3: 并发控制**
        *   **GIVEN** 有超过100条待处理对话
        *   **WHEN** 定时任务执行
        *   **THEN** 通过监控或日志，应能确认系统在同一时间点，最多只向AICO API发起了5个并发请求。
---
*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: 纯后端服务
    *   **后端 (Backend)**:
        *   实现一个定时任务调度器（Scheduler）。
        *   实现一个`AicoExtractionService`，其核心是包含一个固定大小（5个）线程池的执行器。该服务封装了API调用、响应解析和数据库状态更新的全流程。
    *   **数据库 / 存储 (Database / Storage)**:
        *   **读取**: `prepared_conversations`
        *   **写入**: `pending_faqs`
*   **数据模型 / 接口契约 (Data Contracts & APIs)**:

    *   **调用的外部API: AICO智能体**
        *   **Endpoint**: `POST http://20.17.39.169:11105/aicoapi/gateway/v2/chatbot/api_run/1765187112_d4db36b1-5ef3-48f7-85b7-b35e9da02f96` (示例URL，应在配置中)
        *   **Headers**: `Content-Type: application/json`, `Authorization: Bearer {api_key}`
        *   **Request Body**: `{"query": "{conversation_full_text}", "stream": false}`
        *   **Success Response (Expected `data.text[0]` string format)**:
            *   `"问题：...\n答案：..."` 或 `"否"`

*   **约束与边界 (Constraints & Boundaries)**:
    *   **配置硬编码**: AICO智能体的URL、API Key以及核心提示词（Prompt）均由AICO平台侧进行配置。本服务仅在应用的配置文件中硬编码URL和API Key，**不设立**动态配置的数据库表或管理API。
    *   **单一智能体**: 本版本不区分业务场景（水务/公交），所有对话均调用同一个AICO智能体API。
*   **非功能性需求 (Non-Functional)**:
    *   **性能**: 系统必须支持**5个并发**地调用AICO API。
    *   **可观测性**: 需记录每次任务的开始/结束时间、处理的总对话数、成功提取数、返回"否"的数量、失败数及错误详情。