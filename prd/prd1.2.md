# 产品需求文档：对话数据预处理与聚合模块 - V1.2

## 1. 综述 (Overview)
### 1.1 项目背景与核心问题
本系统需要处理的原始对话数据以“流水式”单句形式存储在源数据库中，无法直接用于AI模型的上下文分析。为确保后续AI质检与FAQ提取的准确性，必须先将这些碎片化的对话记录，聚合成结构清晰、人类可读的“会话式”完整对话。V1.2版本的核心目标是构建一个独立的、自动化的后台数据处理模块，专门负责此项数据预处理工作，为后续的所有AI处理环节提供高质量、标准化的数据输入。

### 1.2 核心业务流程 / 用户旅程地图
V1.2版本是一个纯后端的、无人值守的数据处理模块，其核心流程如下：
1.  **阶段一：定时调度** - 系统在每日指定时间（凌晨01:00）自动唤醒处理任务。
2.  **阶段二：数据聚合与转换** - 任务从源数据库中拉取前一日的增量对话数据，并行地将碎片化的对话记录聚合成完整的、带说话人标识的对话文本。
3.  **阶段三：入库待处理** - 将处理完成的完整对话文本，存入一个新的中间数据表（`prepared_conversations`），并标记为“待处理”，以供后续的AI处理模块（V1.3及以后版本）消费。

## 2. 用户故事详述 (User Stories)

### 阶段一：数据预处理流水线

---

#### **US-1.2: 作为后台系统，我需要自动地将源数据库中的零散对话记录转换并聚合成完整的对话文本，以便为AI模型准备好标准化的输入数据。**
*   **价值陈述 (Value Statement)**:
    *   **作为** 后台系统
    *   **我希望** 能够通过一个定时的、高性能的批处理任务，自动完成每日对话数据的抽取、转换和加载（ETL）
    *   **以便于** 将原始的、碎片化的数据转化为结构化的、可供AI直接使用的标准数据格式，并为后续所有智能处理环节提供稳定、可靠的数据基础。
*   **业务规则与逻辑 (Business Logic)**:
    1.  **定时触发 (Scheduling)**:
        *   系统内置一个定时任务调度器，配置为在**每日凌晨01:00**自动执行。
    2.  **数据范围 (Data Scoping)**:
        *   任务启动后，自动计算出执行日期的前一天（T-1）作为目标数据处理范围。
    3.  **数据抽取与转换 (Extraction & Transformation)**:
        *   任务需连接到源数据库`people_customer_dialog`表。
        *   系统**分场景**（如根据`group_code`区分“水务”、“公交”）并行处理。
        *   对于每个场景，系统筛选出T-1时间范围内的所有对话记录。
        *   通过`call_id`对记录进行分组，并严格按照`create_time`（或`seq`）排序。
        *   将属于同一个`call_id`的多行`text`记录，根据`source`字段（1=市民, 2=客服）添加“市民：”或“客服：”前缀，并用换行符`\n`拼接成一个单一的、完整的对话文本字符串。
    4.  **数据加载 (Loading)**:
        *   将聚合、格式化后的完整对话文本，连同`call_id`、`group_code`等关键元数据，插入到本系统自建的`prepared_conversations`表中。
        *   新插入的数据，其AI处理状态`status`字段默认为`unprocessed`。
    5.  **任务执行互斥性**:
        *   调度器需确保同一时间只有一个数据处理任务实例在运行，防止任务重叠造成的数据冲突。
*   **验收标准 (Acceptance Criteria)**:
    *   **场景1: 定时任务成功执行**
        *   **GIVEN** 源数据库中昨天有10条属于`call_id_A`的对话记录
        *   **WHEN** 时间到达今天凌晨01:01
        *   **THEN** 在`prepared_conversations`表中，应能找到一条新的记录，其`call_id`为`call_id_A`，且其`full_text`字段是由那10条记录按正确顺序和格式拼接成的完整对话。
    *   **场景2: 数据处理幂等性**
        *   **GIVEN** 昨天的任务已成功执行
        *   **WHEN** 我手动重新触发一次昨天的任务
        *   **THEN** `prepared_conversations`表中的总记录数不应增加，已存在的`call_id_A`记录不应被重复插入。
---
*   **技术实现概要 (Technical Implementation Brief)**:
    *   **影响范围**: 纯后端服务，数据库
    *   **后端 (Backend)**:
        *   引入定时任务调度框架（如Spring Task, Quartz, Celery Beat等）。
        *   实现一个核心的`DialogETLService`，负责数据处理的全流程。
        *   该服务在处理数据时，应采用多线程或异步任务的方式，实现**数据整理成组的并发**，以提升处理效率。
    *   **数据库 / 存储 (Database / Storage)**:
        *   **数据源 (Read)**: `people_customer_dialog` 表。
        *   **数据目标 (Write)**: `prepared_conversations` 表。
*   **数据模型 / 接口契约 (Data Contracts & APIs)**:
    *   **核心产出表结构 `prepared_conversations`**:
        ```sql
        CREATE TABLE `prepared_conversations` (
          `id` bigint NOT NULL AUTO_INCREMENT,
          `group_code` varchar(2) NOT NULL COMMENT '所属场景 (水务/公交)',
          `call_id` varchar(64) NOT NULL COMMENT '唯一的通话ID',
          `full_text` longtext COMMENT '聚合与格式化后的完整对话文本',
          `status` varchar(20) DEFAULT 'unprocessed' COMMENT 'AI处理状态: unprocessed, processing, completed, failed',
          `conversation_time` datetime COMMENT '对话发生时间，可取该call_id下第一条记录的create_time',
          `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`),
          UNIQUE KEY `uk_call_id` (`call_id`) COMMENT '用call_id做唯一约束，防止重复处理'
        ) COMMENT='预处理完成的对话表，等待AI加工';
        ```
*   **约束与边界 (Constraints & Boundaries)**:
    *   V1.2版本**不涉及**任何对外部AI模型的调用。其职责边界清晰地截止于将处理好的数据存入`prepared_conversations`表。
*   **非功能性需求 (Non-Functional)**:
    *   **性能**: 系统需支持**数据整理的并发处理**。对于日均3400通对话的数据量，整个批处理任务应在**5分钟内**完成。
    *   **可维护性**: 需要提供一个手动的触发机制（如一个API端点或脚本），用于历史数据回溯或在自动任务失败后进行手动补偿。
    *   **可观测性 (Observability)**: 任务执行过程需有详细的日志，记录开始/结束时间、处理的场景、总对话数、成功数、失败数及错误详情。
*   **开放问题与待确认事项 (Open Questions & Follow-ups)**:
    *   后续版本（V1.3）将基于本版本产出的`prepared_conversations`表，进行AI模型的并发调用与处理。