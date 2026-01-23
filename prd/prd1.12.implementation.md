# V1.12「分类知识库展示模块」落地方案（研发视角）

本文档用于把 `prd/prd1.12.md` 落到可实现的研发任务与技术方案；不替代 PRD。

## 0. 需要先拍板的 3 个点（不拍板也能做，但会影响默认行为）

1. **登录后默认落点**：PRD 写“自动进入分类知识库页面”，但现有系统默认进入 `/review`。
   - 选项A（严格按 PRD）：登录后默认跳 `/taxonomy`（分类知识库）；审核工作台仍在侧边栏。
   - 选项B（兼容现状）：仍默认 `/review`，但侧边栏新增“分类知识库”，用户手动进入。
2. **维护权限**：PRD区分“维护者”，现有 `users.role` 目前未做强校验。
   - 选项A：`role in {admin, maintainer}` 才允许写；其他仅可读。
   - 选项B：MVP 全员可写（风险较高）。
3. **范围编码**：PRD 的“当前范围”= `水务` / `公交` / `自行车`（公交账号在页签内切换）。
   - 建议后端存 `scope_code`（`water|bus|bike`），CSV/界面仍展示中文，后端做映射校验。

## 1. 现有工程落点（仓库结构映射）

- 前端：`frontend/`（React + Vite + Antd + zustand）
  - 现有路由：`/review`、`/knowledge`、`/login`
  - 现有场景信息：`user.scenarioId`（`frontend/src/store/auth.ts`）
- 后端：`backend/`（FastAPI + SQLAlchemy，MySQL）
  - 认证：`get_current_user`（JWT）
  - 场景隔离：多数接口按 `current_user.scenario_id` 过滤
  - API 版本目录：`backend/app/api/v1_xx/`

本模块与“QA审核模块”业务独立，但复用同一登录体系与导航入口（PRD Wireframe）。

## 2. 数据模型（MySQL DDL 草案）

> 说明：项目目前未提交 Alembic migration 配置；这里先给 DDL，后续可补迁移体系。

### 2.1 分类节点（固定三级）

```sql
CREATE TABLE kb_taxonomy_nodes (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  scope_code VARCHAR(16) NOT NULL COMMENT 'water|bus|bike',
  level TINYINT NOT NULL COMMENT '1|2|3',
  name VARCHAR(128) NOT NULL,
  parent_id BIGINT NULL,
  definition TEXT NULL COMMENT '仅 level=3 使用',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT ck_kb_taxonomy_level CHECK (level IN (1,2,3)),
  CONSTRAINT fk_kb_taxonomy_parent FOREIGN KEY (parent_id) REFERENCES kb_taxonomy_nodes(id)
);

CREATE INDEX idx_kb_taxonomy_nodes_scope_parent ON kb_taxonomy_nodes(scope_code, parent_id);
CREATE UNIQUE INDEX uq_kb_taxonomy_nodes_scope_parent_name ON kb_taxonomy_nodes(scope_code, parent_id, name);
```

约束策略（对应 PRD）：
- `level=1`：`parent_id IS NULL`
- `level=2`：`parent_id` 指向 `level=1`
- `level=3`：`parent_id` 指向 `level=2`，`definition NOT NULL`

（以上可在应用层校验，必要时再补更强 DB 约束。）

### 2.2 对话案例（仅挂三级）

```sql
CREATE TABLE kb_taxonomy_cases (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  node_id BIGINT NOT NULL,
  content MEDIUMTEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_kb_taxonomy_cases_node FOREIGN KEY (node_id) REFERENCES kb_taxonomy_nodes(id) ON DELETE CASCADE
);

CREATE INDEX idx_kb_taxonomy_cases_node ON kb_taxonomy_cases(node_id);
```

## 3. 后端 API 设计（FastAPI）

建议新增路由：`/api/v1.12/kb-taxonomy/...`（与 PRD 版本对齐）。

### 3.1 范围（scope）判定

后端统一把“当前范围”归一为 `scope_code`：
- 水务账号：只允许 `water`
- 公交账号：允许 `bus` / `bike`（由前端 Tab 决定）

实现建议：在 router 里做 `resolve_scope(current_user, requested_scope_code)`，不允许越权则 `403`。

### 3.2 查询/浏览

- `GET /api/v1.12/kb-taxonomy/tree?scope=water`
  - 返回：按同级 `name` 排序的三级树（可返回嵌套结构，前端直接渲染 Tree）
- `GET /api/v1.12/kb-taxonomy/nodes/{id}?scope=...`
  - 返回：节点信息 + 路径（一级/二级/三级）+ `definition`（仅三级）
- `GET /api/v1.12/kb-taxonomy/nodes/{id}/cases?scope=...&keyword=...`
  - 返回：该三级下案例列表（默认全部展开由前端实现），支持关键词过滤（仅当前三级）

### 3.3 分类 CRUD（对应 US-KB-02）

- `POST /api/v1.12/kb-taxonomy/nodes`
  - body：`{ scope, parentId?, level, name, definition? }`
- `PUT /api/v1.12/kb-taxonomy/nodes/{id}`
  - body：`{ scope, name?, definition? }`
- `DELETE /api/v1.12/kb-taxonomy/nodes/{id}?scope=...`
  - 规则：
    - 有子节点：400 + 可操作提示“请先删除/迁移子节点”
    - 删三级且有案例：建议前端二次确认；后端删除时级联删案例（FK ON DELETE CASCADE 或应用层）

### 3.4 案例 CRUD（对应 US-KB-03）

- `POST /api/v1.12/kb-taxonomy/cases`
  - body：`{ scope, nodeId, content }`
- `PUT /api/v1.12/kb-taxonomy/cases/{id}`
  - body：`{ scope, content }`
- `DELETE /api/v1.12/kb-taxonomy/cases/{id}?scope=...`
  - 删除需前端二次确认；后端校验案例所属 `node.scope_code`。

### 3.5 CSV 覆盖导入（对应 US-KB-04）

为匹配“校验 -> 二次确认 -> 覆盖导入”的状态机，建议两步接口：

- `POST /api/v1.12/kb-taxonomy/import/validate?scope=...`（multipart file，支持 `.csv` / `.xlsx`）
  - 解析 CSV 表头：固定列 `业务域, 一级, 二级, 三级, 定义` + 动态列（列名以“案例”开头）
  - 返回：
    - `ok: true` 时给出 summary（`三级分类数`、`案例数`）
    - `ok: false` 时返回 errors：至少包含 `row, column, message, expected, actual`
- `POST /api/v1.12/kb-taxonomy/import/execute?scope=...`（multipart file，支持 `.csv` / `.xlsx`）
  - 先做同样校验（避免绕过 validate）
  - 使用事务保证原子性：删除该 scope 全部旧数据 -> 导入新数据 -> commit；失败 rollback

校验/合并规则（严格按 PRD）：
- 域一致性：CSV 每行 `业务域` 必须等于当前范围（中文名）；
- 必填：`业务域/一级/二级/三级/定义` 非空；
- 定义一致性：同一路径多行 `定义` 必须完全一致，否则整批失败，并指出冲突行号；
- 合并：同一路径多行合并为一个三级；案例“追加”；案例不去重；空案例列忽略。

## 4. 前端页面落地（React + Antd）

### 4.1 路由与导航

- 新增页面：`/taxonomy`（命名可调整）
- `frontend/src/App.tsx` 侧边栏 `Menu` 新增“分类知识库”
- 登录后默认路由按“0.1 登录落点”拍板执行

### 4.2 页面结构（对齐 PRD 线框）

- 顶部：复用现有 Header（用户信息/退出）
- 主体：左右分栏
  - 左：搜索框 + 三级 Tree（同级按名称排序）+ 节点更多操作（新增子节点/重命名/删除）
  - 右：路径 + 三级定义 + 案例列表（默认全部展开）+ 案例关键词过滤 + 新增/编辑/删除
- 公交账号：在页面顶部展示 Tabs：`公交` / `自行车`，切换时刷新 tree 与详情

### 4.3 CSV 导入交互

- 页面按钮：`导入CSV（覆盖当前范围）`
- Modal：`开始校验` -> 展示校验结果（成功：将导入 X/Y；失败：错误列表）-> `确认覆盖并导入`

## 5. 分期交付（建议）

1. **M1（只读闭环）**：树+三级详情+案例列表（默认展开）+空态与加载失败提示
2. **M2（分类 CRUD）**：增/改/删 + 删除约束提示 + 排序刷新
3. **M3（案例 CRUD）**：增/改/删 + 三级内关键词过滤
4. **M4（CSV 覆盖导入）**：validate + execute + 错误展示（含行号/列名）
5. **M5（稳态）**：权限收敛、并发导入保护、性能优化（大案例默认虚拟滚动/分页可选）

## 6. QA/验收清单（最小集）

- 场景隔离：水务无 Tabs；公交有 Tabs；切换 Tabs 数据不串
- 树排序：同级按名称排序
- 删除约束：有子节点不可删；删三级需二次确认；删三级后案例一起删
- 案例默认展开：进入三级详情即看到全文
- CSV 校验：域不一致/必填缺失/定义冲突能报“行号+列名+原因+期望/实际”
- CSV 合并：同一路径多行合并；案例不去重；空案例列忽略
- 覆盖导入原子性：导入失败不改变原数据；成功后全量替换
