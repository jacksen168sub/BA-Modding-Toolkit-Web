# BA-Modding-Toolkit-Web

[![Docker Build](https://github.com/jacksen168sub/BA-Modding-Toolkit-Web/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/jacksen168sub/BA-Modding-Toolkit-Web/actions/workflows/docker-publish.yml)
[![GitHub release](https://img.shields.io/github/v/release/jacksen168sub/BA-Modding-Toolkit-Web?include_prereleases)](https://github.com/jacksen168sub/BA-Modding-Toolkit-Web/releases)
[![Docker Pulls](https://img.shields.io/docker/pulls/jacksen168/ba-modding-toolkit-web)](https://hub.docker.com/r/jacksen168/ba-modding-toolkit-web)
[![License](https://img.shields.io/github/license/jacksen168sub/BA-Modding-Toolkit-Web)](LICENSE)

为 [BA-Modding-Toolkit](https://github.com/Agent-0808/BA-Modding-Toolkit) 构建的 Web 服务平台，支持多用户自助式使用。

**[English](../README.md)**

## 功能特性

- **Mod 更新** - 将旧版 Mod 更新到最新游戏版本
- **资源打包** - 将资源文件打包成游戏 Bundle
- **资源解包** - 从游戏 Bundle 中提取资源
- **CRC 校验** - 计算并修复文件 CRC 校验值
- **服务状态** - 在 `/status` 查看任务总数、队列长度与主机/容器负载

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + SQLite |
| 前端 | Vue 3 + Vite + Element Plus |
| 部署 | Docker Compose |

## 快速开始

### 方式一：生产模式（推荐）

构建前端并启动后端，所有服务运行在 **8000 端口**：

```bash
# 1. 构建前端
cd frontend
npm install
npm run build
cd ..

# 2. 启动后端（自动托管前端静态文件）
cd backend
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
cd ..
```

访问 http://localhost:8000

### 方式二：开发模式

前后端分离运行，支持热重载：

**终端 1 - 启动后端：**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**终端 2 - 启动前端：**
```bash
cd frontend
npm install
npm run dev
```

- 前端访问：http://localhost:3000
- 后端 API：http://localhost:8000
- 前端会自动代理 `/api` 请求到后端

### 方式三：Docker（端口 80）

#### 使用 Docker Compose（本地构建）

```bash
docker-compose up --build
```

访问 http://localhost

#### 使用预构建镜像

从 GitHub Container Registry 拉取镜像：

```bash
# 拉取镜像
docker pull ghcr.io/jacksen168sub/ba-modding-toolkit-web:latest

# 运行容器
docker run -d \
  --name bamt-web \
  -p 80:80 \
  -v ./storage:/app/storage \
  -v ./data:/app/data \
  ghcr.io/jacksen168sub/ba-modding-toolkit-web:latest
```

访问 http://localhost

#### 可选配置

| 参数 | 说明 |
|------|------|
| `-p 80:80` | 端口映射，格式为 `主机端口:容器端口` |
| `-v ./storage:/app/storage` | 持久化文件存储 |
| `-v ./data:/app/data` | 持久化数据库 |

#### Docker Hub

也可从 DockerHub 拉取：

```bash
docker pull jacksen168/ba-modding-toolkit-web:latest
```

## 项目结构

```
BA-Modding-Toolkit-Web/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 应用入口
│   │   ├── routers/         # API 路由
│   │   ├── services/        # 业务逻辑
│   │   ├── models/          # 数据模型
│   │   └── utils/           # 工具函数
│   └── pyproject.toml
├── frontend/                # Vue 3 前端
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   ├── components/      # 通用组件
│   │   ├── api/             # API 封装
│   │   └── stores/          # 状态管理
│   └── package.json
├── storage/                 # 文件存储
│   ├── uploads/             # 用户上传
│   └── outputs/             # 处理结果
├── data/                    # SQLite 数据库
└── upstream/                # BA-Modding-Toolkit 子模块
```

## 环境要求

- Python >= 3.10
- Node.js >= 18
- uv（Python 包管理器）

## 配置

后端配置位于 `backend/app/config.py`，支持环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| UPLOAD_DIR | 上传文件目录 | storage/uploads |
| OUTPUT_DIR | 输出文件目录 | storage/outputs |
| SESSION_EXPIRE_HOURS | 会话过期时间 | 24 |
| CLI_COMPRESSION | Bundle 压缩方式 (lzma, lz4, original, none) | lz4 |
| STATUS_CONTAINER_AWARE | 读取本容器的 cgroup 限额，而非宿主机总量 | true |
| STATUS_REDACT | 需要从 `/api/status` 中隐去的细项，逗号分隔 | （空） |

### 隐去状态页上的信息

`GET /api/status` 与 `/status` 页面可以对外公开，而不必暴露硬件配置或访问量。
每个细项都可以单独隐去，例如只隐藏 CPU 占用而保留磁盘信息，或隐藏存储路径
但保留用量数据：

| 细项 | 隐去的内容 |
|------|-----------|
| `cpu` | CPU 使用率、有效核心数、负载均值 |
| `memory` | 内存总量 / 已用 / 可用 / 百分比 |
| `disk` | 磁盘总量 / 已用 / 可用 / 百分比 |
| `paths` | 存储卷的文件系统路径 |
| `host` | 宿主机核心数与内存总量 |
| `container` | 容器运行时、cgroup 版本、CPU 配额与内存限额 |
| `process` | 后端进程 PID、内存、CPU、线程数、启动时间 |
| `version` | 应用版本号与提交哈希 |
| `uptime` | 运行时长与启动时间 |
| `tasks` | 任务总数与状态 / 类型分布 |
| `performance` | 成功率与平均耗时 |
| `activity` | 近期任务量（1 小时 / 24 小时 / 7 天） |
| `queue` | 队列长度与工作进程占用 |
| `storage` | 上传 / 结果文件的数量与体积 |
| `sessions` | 会话数量 |

另有两个简写：`system` 等于 `cpu,memory,disk`，`all` 等于以上全部。无法识别的
条目会被忽略，也就是说拼错时该项会被**保留显示**而非隐藏——请检查响应的
`redacted` 数组以确认实际生效的细项。

被隐去的字段以 `null` 返回，并列入响应的 `redacted` 数组；页面会显示提示并列出
被隐去的细项，相应位置以 `—` 代替（进度条会换成斜纹占位块，而不是误导性的
`0%`）。

```bash
# 隐藏机器负载与存储位置
STATUS_REDACT=cpu,memory,disk,paths

# 保留资源图表，但不透露宿主机与构建信息
STATUS_REDACT=host,container,process,version,uptime

# 全部隐去
STATUS_REDACT=all
```

在容器中运行时，CPU 与内存按容器自身的 cgroup 限额统计，与实际分配的资源
一致。设置 `STATUS_CONTAINER_AWARE=false` 可恢复为宿主机口径。

## 自定义页面注入

Docker 镜像把前端保留为一份**原始模板**，并在每次容器启动时渲染到 Web 根目录。这样
你可以往页面里加入自己的 HTML——额外样式、公告横幅、反馈按钮——而**无需重新构建镜像**，
也让公开的镜像本身不含任何与部署环境相关的内容。

内容会插入到 Vite 在 `index.html` 中保留的两个标记处：

| 位置 | 环境变量 | 挂载文件（优先于环境变量） |
|------|----------|----------------------------|
| `</head>` 之前 | `INJECT_HEAD_HTML` | `/app/data/inject-head.html` |
| `</body>` 之前 | `INJECT_BODY_HTML` | `/app/data/inject-body.html` |

推荐用文件，因为多行 HTML 在 shell 或 compose 文件里转义很麻烦。可用
`INJECT_HEAD_FILE` / `INJECT_BODY_FILE` 覆盖默认路径。两者都不配置则不做任何注入。

```bash
# 推荐：把片段放进与数据库同级的文件
cat > data/inject-head.html <<'EOF'
<!-- 你的 HTML -->
EOF

docker run -d --name bamt-web -p 80:80 \
  -v ./storage:/app/storage \
  -v ./data:/app/data \
  ghcr.io/jacksen168sub/ba-modding-toolkit-web:latest
```

每次启动都会从模板重新渲染，因此修改文件（或环境变量）后重启容器即可生效；不配置时
页面保持原样。

### 单页应用（SPA）

这是一个 Vue 单页应用：在各工具页之间跳转不会重新加载文档，因此只对文档加载做出反应的
片段只会触发一次。应用暴露了一个钩子，供注入的内容跟随页内跳转：

```js
// path 可安全使用；fullPath 可能带有 taskId 查询参数。
window.__bamtRouteChange = ({ path, fullPath }) => { /* ... */ }
```

### 关于信任边界

注入在本质上就是"向页面输出任意 HTML/JS"——与直接改文件同等的权限。它是给自托管实例的
操作者自己用的，所以请务必自己保管这些变量：不要通过 API 暴露它们，也不要让应用用户能
设置它们。注入**仅对 Docker 镜像生效**；本地生产模式（`start-prod.ps1`）直接托管构建
产物，不会注入。

## 支持的语言

界面支持多种语言：

- English (en-US)
- 简体中文 (zh-CN)
- 繁體中文 (zh-TW)
- 日本語 (ja-JP)
- 한국어 (ko-KR)
- Español (es-ES)
- Français (fr-FR)
- Русский (ru-RU)
- العربية (ar-SA)
- हिन्दी (hi-IN)
- বাংলা (bn-BD)
- ไทย (th-TH)

## 致谢

- [BA-Modding-Toolkit](https://github.com/Agent-0808/BA-Modding-Toolkit) - 上游 CLI 工具

## License

GNU General Public License v3.0
