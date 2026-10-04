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
| STATUS_REDACT | 需要从 `/api/status` 中隐去的字段，逗号分隔 | （空） |

### 隐去状态页上的信息

`GET /api/status` 与 `/status` 页面可以对外公开，而不必暴露硬件配置。将
`STATUS_REDACT` 设为需要隐去的字段列表即可：

| 字段 | 隐去的内容 |
|------|-----------|
| `system` | CPU、内存、磁盘的使用率数值 |
| `host` | 宿主机核心数/内存总量，以及容器 / cgroup 详情 |
| `process` | 后端进程的 PID、内存与线程数 |
| `paths` | 存储卷的文件系统路径 |
| `version` | 应用版本号与提交哈希 |
| `storage` | 上传 / 结果文件的数量与体积 |
| `sessions` | 会话数量 |

`all` 表示隐去以上全部。任务与队列计数不会被隐去，页面仍然可用。被隐去的
字段以 `null` 返回，并列入响应的 `redacted` 数组；页面会显示提示，相应位置
以 `—` 代替。

```bash
# 示例：页面照常公开，但不透露宿主机与版本信息
STATUS_REDACT=host,process,paths,version
```

在容器中运行时，CPU 与内存按容器自身的 cgroup 限额统计，与实际分配的资源
一致。设置 `STATUS_CONTAINER_AWARE=false` 可恢复为宿主机口径。

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
