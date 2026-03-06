# BA-Modding-Toolkit-Web

为 [BA-Modding-Toolkit](https://github.com/Agent-0808/BA-Modding-Toolkit) 构建的 Web 服务平台，支持多用户自助式使用。

## 功能特性

- **Mod 更新** - 更新游戏 Mod 文件
- **资源打包** - 将资源文件打包成游戏格式
- **资源解包** - 解包游戏资源文件
- **CRC 校验** - 计算文件 CRC 校验值

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

## License

MIT
