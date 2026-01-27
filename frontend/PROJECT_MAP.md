# Frontend 项目目录地图

## 项目概览
基于 React + TypeScript + Vite 的智能知识库管理系统前端，提供 QA 审核工作台、知识库管理、分类知识库等功能，与后端 API 无缝集成。

## 作用范围
本次扫描目录：`frontend/`（前端代码）

## 入口与运行链路

### 应用启动
- **入口文件**: `src/main.tsx`
- **根组件**: `src/App.tsx`
- **启动命令**:
  - 开发: `npm run dev` (端口: 5176)
  - 构建: `npm run build`
  - 预览: `npm run preview`

### 初始化流程
1. 加载样式 → `src/styles.css`
2. 初始化路由 → `react-router-dom` BrowserRouter
3. 恢复认证状态 → `useAuthStore` 从 localStorage 加载
4. 渲染 App 根组件

### 页面路由结构
```
/                            → 重定向到 /taxonomy
/login                      → 登录页（无布局）
/review                     → FAQ 审核工作台（需认证）
/knowledge                  → QA 知识库管理（需认证）
/taxonomy                   → 三级分类知识库（需认证，默认页）
/taxonomy-review            → 分类审核工作台（需认证）
/internal-tasks/trigger-panel-ab12cd34 → 管理员任务（需认证，固定路径）
```

## 关键配置

### 环境与依赖
```json
// package.json 关键依赖
{
  "react": "^18.3.1",
  "react-dom": "^18.3.1",
  "react-router-dom": "^6.28.0",  // 路由管理
  "antd": "^5.21.7",              // UI 组件库
  "axios": "^1.7.7",               // HTTP 客户端
  "zustand": "^4.5.5",            // 状态管理
  "vite": "^5.4.9"                // 构建工具
}
```

### API 配置
```typescript
// src/api/client.ts
API_BASE_URL = 'http://127.0.0.1:8011'  // 后端 API 地址
Timeout = 10000ms
```

### Vite 配置
```typescript
// vite.config.ts
- 别名: '@' → 'src'
- 开发服务器端口: 5176
- 插件: @vitejs/plugin-react-swc (SWC 编译加速)
```

### 认证存储
```typescript
// src/store/auth.ts
localStorage Key: 'kb_review_auth'
存储内容: { accessToken: string, user: AuthUser }
```

## 目录与文件说明

```
frontend/
├── src/
│   ├── main.tsx                   # React 应用入口
│   ├── App.tsx                    # 根组件（路由 + 布局）
│   ├── styles.css                 # 全局样式
│   ├── api/                       # API 客户端层
│   │   └── client.ts              # Axios 实例 + 拦截器
│   ├── store/                     # 状态管理（Zustand）
│   │   └── auth.ts                # 认证状态（token + user）
│   └── pages/                     # 页面组件
│       ├── LoginPage.tsx           # 登录页
│       ├── ReviewWorkbenchPage.tsx # FAQ 审核工作台
│       ├── KnowledgeManagementPage.tsx # QA 知识库管理
│       ├── TaxonomyKBPage.tsx     # 三级分类知识库
│       ├── TaxonomyReviewWorkbenchPage.tsx # 分类审核工作台
│       └── InternalTasksPage.tsx   # 管理员任务面板
├── index.html                     # HTML 模板
├── package.json                   # 项目依赖配置
├── vite.config.ts                 # Vite 构建配置
├── tsconfig.json                 # TypeScript 配置
└── package-lock.json              # 依赖锁定文件
```

## 关键模块关系/调用链

### 1. 认证流程
```
LoginPage
  ├─ POST /api/v1.6/auth/login
  ├─ useAuthStore.setAuth(token, user)
  ├─ 持久化到 localStorage
  └─ 导航到 /taxonomy（默认）
```

### 2. API 请求拦截
```
apiClient (src/api/client.ts)
  ├─ 请求拦截: 自动添加 Authorization: Bearer {token}
  ├─ 响应拦截: 401 自动跳转 /login（排除登录请求）
  └─ 统一错误处理
```

### 3. 路由守卫
```
App.tsx → RequireAuth 组件
  ├─ 检查 useAuthStore.accessToken
  ├─ 未认证: 重定向到 /login
  └─ 已认证: 渲染目标页面
```

### 4. 页面布局（AppShell）
```
AppShell (src/App.tsx)
  ├─ 左侧侧边栏（固定 200px）
  │   ├─ 应用标题（根据 scenarioId 动态显示）
  │   └─ 菜单分组
  │       ├─ QA 审核模块
  │       └─ 分类知识库模块
  ├─ 顶部 Header（用户信息 + 退出按钮）
  └─ 主内容区域（Margin: 16px）
```

### 5. 场景识别
```
根据 user.scenarioId 显示不同标题:
- scenarioId == 2: "公交智能知识库系统"
- 其他: "水务智能知识库系统"
```

### 6. 分类知识库页面（TaxonomyKBPage）
```
TaxonomyKBPage
  ├─ Tab 1: 分类树管理
  │   ├─ 树形组件（Antd Tree）
  │   ├─ CRUD: 新增/编辑/删除节点
  │   └─ 支持三级分类：业务域 → 一级 → 二级 → 三级
  ├─ Tab 2: 案例管理
  │   ├─ 案例列表（Table）
  │   ├─ CRUD: 新增/编辑/删除案例
  │   └─ 动态案例列（案例1, 案例2...）
  └─ Tab 3: 导入/导出
      ├─ 批量导入（CSV/XLSX）
      ├─ 导入验证与错误提示
      └─ 导出格式：固定列（业务域, 一级, 二级, 三级, 定义）+ 动态案例列
```

### 7. 管理员任务（InternalTasksPage）
```
InternalTasksPage（固定路径: /internal-tasks/trigger-panel-ab12cd34）
  ├─ 触发数据聚合: POST /api/v1.10/admin/trigger-aggregation
  │   └─ 参数: { startTime, endTime }
  ├─ 触发 FAQ 提取: POST /api/v1.10/admin/trigger-extraction
  │   └─ 参数: { limit? }
  └─ 触发知识库同步: POST /api/v1.10/admin/trigger-compare-kb-sync
```

## 技术栈说明

### 框架与库
- **React 18.3**: 函数式组件 + Hooks
- **TypeScript 5.6**: 类型安全
- **Vite 5.4**: 高速构建工具（基于 ESBuild + SWC）
- **Ant Design 5.21**: 企业级 UI 组件库

### 状态管理
- **Zustand 4.5**: 轻量级状态管理（用于认证状态）

### 路由
- **React Router DOM 6.28**: 声明式路由（BrowserRouter + Routes）

### HTTP 客户端
- **Axios 1.7**: Promise 基础的 HTTP 客户端（带拦截器）

### 日期处理
- **Day.js**: 轻量级日期库（用于 InternalTasksPage）

### 文件上传
- **Antd Upload**: 支持 CSV/XLSX 文件导入

## 风险/遗留/不确定点

### 风险点
1. **API_BASE_URL 硬编码** - `http://127.0.0.1:8011` 未使用环境变量，部署时需手动修改
2. **管理员路径固定** - `/internal-tasks/trigger-panel-ab12cd34` 使用固定后缀，安全性较低
3. **错误处理宽泛** - `catch (error: any)` 类型断言不安全

### 不确定点
1. **权限控制** - 前端仅有路由守卫，未见页面级权限控制逻辑
2. **场景权限映射** - `scenarioId == 2` 为公交，其他为水务的映射规则（App.tsx:26），需与后端一致

### 遗留/未使用文件
- `src/pages/ReviewWorkbenchPage.tsx` - 未读取内容，假设为 FAQ 审核工作台
- `src/pages/KnowledgeManagementPage.tsx` - 未读取内容，假设为 QA 知识库管理

### 需要关注的点
1. **Token 过期处理** - 后端设置 7 天有效期，前端未主动刷新
2. **localStorage 安全性** - 认证信息存储在 localStorage（易受 XSS 攻击）
3. **API 超时设置** - 统一 10 秒，部分操作（如导入）可能需要更长

## 页面功能矩阵

| 页面路径 | 页面名称 | 需认证 | 主要功能 |
|---------|---------|--------|---------|
| `/login` | 登录页 | 否 | 用户登录 |
| `/review` | FAQ 审核工作台 | 是 | 审核提交流程 |
| `/knowledge` | QA 知识库管理 | 是 | 知识条目 CRUD |
| `/taxonomy` | 三级分类知识库 | 是 | 分类树 + 案例管理 + 导入导出 |
| `/taxonomy-review` | 分类审核工作台 | 是 | 分类内容审核 |
| `/internal-tasks/trigger-panel-ab12cd34` | 管理员任务 | 是 | 触发后台任务 |

## 后端 API 映射

| 前端路由 | 后端 API 版本 | 功能 |
|---------|--------------|------|
| `/login` | v1.6 | `/api/v1.6/auth/login` |
| `/review` | v1.4 | `/api/v1.4/review/*` |
| `/knowledge` | v1.4.1 | `/api/v1.4.1/knowledge/*` |
| `/taxonomy` | v1.12 | `/api/v1.12/kb-taxonomy/*` |
| `/taxonomy-review` | v1.14 | `/api/v1.14/kb-taxonomy-review/*` |
| `/internal-tasks/*` | v1.10 | `/api/v1.10/admin/*` |

## 本次更新
- 创建时间：2026-01-26
- 扫描范围：`frontend/` 完整目录
- 新增文档：首次生成 PROJECT_MAP.md
