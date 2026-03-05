# BA-Modding-Toolkit-Web 实现计划

## 项目概述

为 [BA-Modding-Toolkit](https://github.com/Agent-0808/BA-Modding-Toolkit) 构建一个 Web 服务平台，
支持多用户自助式使用，无需登录，通过 UUID 追踪会话和任务。

---

## 技术栈

| 组件 | 技术选型 |
|------|----------|
| 上游代码管理 | Git Submodule |
| 数据库 | SQLite + SQLAlchemy |
| 后端框架 | FastAPI |
| 异步任务 | FastAPI BackgroundTasks |
| 前端框架 | Vue 3 + Vite + Pinia + Element Plus |
| 部署方式 | Docker Compose |

---

## 目录结构

```
BA-Modding-Toolkit-Web/
│
├── upstream/                              # Git Submodule: 上游项目
│   └── BA-Modding-Toolkit/
│
├── backend/                               # FastAPI 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI 入口
│   │   ├── config.py                      # 配置管理
│   │   │
│   │   ├── routers/                       # API 路由
│   │   │   ├── __init__.py
│   │   │   ├── session.py                 # 用户会话 API
│   │   │   ├── tasks.py                   # 任务管理 API
│   │   │   ├── files.py                   # 文件上传/下载 API
│   │   │   ├── update.py                  # Mod 更新 API
│   │   │   ├── pack.py                    # 资源打包 API
│   │   │   ├── extract.py                 # 资源解包 API
│   │   │   └── crc.py                     # CRC 校验 API
│   │   │
│   │   ├── services/                      # 业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── session_service.py         # 会话管理
│   │   │   ├── task_service.py            # 任务管理
│   │   │   ├── file_service.py            # 文件存储
│   │   │   └── cli_runner.py              # CLI 命令执行
│   │   │
│   │   ├── models/                        # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── database.py                # SQLite 数据库连接
│   │   │   ├── session.py                 # 会话表模型
│   │   │   ├── task.py                    # 任务表模型
│   │   │   ├── file.py                    # 文件表模型
│   │   │   └── schemas.py                 # Pydantic 请求/响应模型
│   │   │
│   │   └── utils/                         # 工具函数
│   │       ├── __init__.py
│   │       └── cleanup.py                 # 过期数据清理
│   │
│   ├── pyproject.toml
│   └── requirements.txt
│
├── frontend/                              # Vue 3 前端
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── api/                           # API 封装
│   │   ├── utils/                         # 工具函数
│   │   ├── stores/                        # Pinia 状态管理
│   │   ├── pages/                         # 页面组件
│   │   ├── components/                    # 通用组件
│   │   ├── styles/
│   │   └── router/
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── storage/                               # 文件存储
│   ├── uploads/{uuid}/                    # 用户上传文件
│   ├── outputs/{uuid}/                    # 处理结果文件
│   └── temp/                              # 临时文件
│
├── data/                                  # 数据库文件
│   └── bamt.db
│
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── nginx.conf
├── .gitignore
└── .gitmodules
```

---

## 数据库设计

### SQLite 表结构

```sql
-- 用户会话表
CREATE TABLE sessions (
    uuid TEXT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME DEFAULT (datetime('now', '+24 hours')),
    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 任务表
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    session_uuid TEXT NOT NULL,
    type TEXT NOT NULL,           -- 'update', 'pack', 'extract', 'crc'
    status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    options TEXT,                  -- JSON 格式的任务参数
    error_message TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    expires_at DATETIME DEFAULT (datetime('now', '+24 hours')),
    FOREIGN KEY (session_uuid) REFERENCES sessions(uuid)
);

-- 文件表
CREATE TABLE files (
    id TEXT PRIMARY KEY,
    session_uuid TEXT NOT NULL,
    task_id TEXT,
    type TEXT NOT NULL,            -- 'input', 'output'
    original_name TEXT,
    stored_path TEXT,
    size INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME DEFAULT (datetime('now', '+24 hours')),
    FOREIGN KEY (session_uuid) REFERENCES sessions(uuid),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 索引
CREATE INDEX idx_tasks_session ON tasks(session_uuid);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_files_session ON files(session_uuid);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
CREATE INDEX idx_files_expires ON files(expires_at);
CREATE INDEX idx_tasks_expires ON tasks(expires_at);
```

---

## 过期文件清理机制

### 设计目标

1. 自动清理超过 24 小时的会话、任务、文件
2. 不影响正在进行的任务
3. 可配置清理时间间隔
4. 支持手动触发清理

### 实现方案

#### 方案一：APScheduler 定时任务（推荐）

```python
# backend/app/utils/cleanup.py
from datetime import datetime, timedelta
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from ..models.database import get_db
from ..models.session import Session
from ..models.task import Task
from ..models.file import File
from ..config import settings

scheduler = AsyncIOScheduler()

async def cleanup_expired_data():
    """
    清理过期数据：
    1. 删除过期的数据库记录
    2. 删除对应的物理文件
    """
    db = next(get_db())
    now = datetime.utcnow()
    
    # 1. 清理过期会话
    expired_sessions = db.query(Session).filter(
        Session.expires_at < now
    ).all()
    
    for session in expired_sessions:
        # 删除用户目录下的所有文件
        user_upload_dir = Path(settings.UPLOAD_DIR) / session.uuid
        user_output_dir = Path(settings.OUTPUT_DIR) / session.uuid
        
        if user_upload_dir.exists():
            shutil.rmtree(user_upload_dir)
        if user_output_dir.exists():
            shutil.rmtree(user_output_dir)
        
        # 删除数据库记录 (级联删除 tasks 和 files)
        db.delete(session)
    
    db.commit()
    print(f"[Cleanup] Deleted {len(expired_sessions)} expired sessions")

# 每 1 小时执行一次清理
scheduler.add_job(cleanup_expired_data, 'interval', hours=1)
```

#### 方案二：FastAPI 生命周期钩子

```python
# backend/app/main.py
import asyncio
from contextlib import asynccontextmanager
from .utils.cleanup import cleanup_expired_data

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：启动后台清理任务
    cleanup_task = asyncio.create_task(periodic_cleanup())
    yield
    # 关闭时：取消后台任务
    cleanup_task.cancel()

async def periodic_cleanup():
    """每小时执行一次清理"""
    while True:
        await asyncio.sleep(3600)  # 1小时
        await cleanup_expired_data()

app = FastAPI(lifespan=lifespan)
```

#### 方案三：独立清理脚本（适合生产环境）

```python
# scripts/cleanup.py
"""
独立清理脚本，可通过 cron 或 systemd timer 调用
用法: python -m scripts.cleanup
"""
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from pathlib import Path
import shutil

def cleanup():
    from backend.app.models.database import SessionLocal
    from backend.app.models.session import Session
    from backend.app.config import settings
    
    db = SessionLocal()
    now = datetime.utcnow()
    
    expired = db.query(Session).filter(Session.expires_at < now).all()
    
    for session in expired:
        # 清理文件
        for base_dir in [settings.UPLOAD_DIR, settings.OUTPUT_DIR]:
            user_dir = Path(base_dir) / session.uuid
            if user_dir.exists():
                shutil.rmtree(user_dir)
        
        db.delete(session)
    
    db.commit()
    print(f"Cleaned {len(expired)} expired sessions")

if __name__ == "__main__":
    cleanup()
```

### 清理策略

| 数据类型 | 过期时间 | 清理动作 |
|----------|----------|----------|
| 会话 | 创建后 24 小时 | 删除数据库记录 + 用户文件目录 |
| 任务 | 创建后 24 小时 | 随会话级联删除 |
| 上传文件 | 创建后 24 小时 | 随会话级联删除 |
| 输出文件 | 创建后 24 小时 | 随会话级联删除 |
| 临时文件 | 任务完成后立即 | 任务完成后删除 |

### 配置项

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 文件存储路径
    UPLOAD_DIR: str = "storage/uploads"
    OUTPUT_DIR: str = "storage/outputs"
    TEMP_DIR: str = "storage/temp"
    
    # 过期时间配置
    SESSION_EXPIRE_HOURS: int = 24
    
    # 清理任务配置
    CLEANUP_INTERVAL_HOURS: int = 1
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## API 设计

### 会话管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/session/{uuid}` | 获取会话信息及任务列表 |
| POST | `/api/session/{uuid}/refresh` | 刷新会话过期时间 |

### 文件操作

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/files/upload` | 上传文件（绑定 UUID） |
| GET | `/api/files/download/{file_id}` | 下载文件 |
| DELETE | `/api/files/{file_id}` | 删除文件 |

### 任务管理

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/tasks/update` | 创建 Mod 更新任务 |
| POST | `/api/tasks/pack` | 创建打包任务 |
| POST | `/api/tasks/extract` | 创建解包任务 |
| POST | `/api/tasks/crc` | 创建 CRC 校验任务 |
| GET | `/api/tasks/{task_id}` | 查询任务状态 |
| GET | `/api/tasks/{task_id}/result` | 获取任务结果文件 |

---

## 实现步骤

### 阶段 1：项目初始化

1. 添加上游为 Git Submodule
   ```bash
   git submodule add https://github.com/Agent-0808/BA-Modding-Toolkit.git upstream/BA-Modding-Toolkit
   ```

2. 创建目录结构
   ```bash
   mkdir -p backend/app/{routers,services,models,utils}
   mkdir -p frontend/src/{api,utils,stores,pages,components,styles,router}
   mkdir -p storage/{uploads,outputs,temp}
   mkdir -p data
   ```

### 阶段 2：后端核心开发

1. 数据库模型
   - 配置 SQLite 连接
   - 创建 Session, Task, File 模型
   - 实现数据库初始化

2. API 路由
   - session.py: 会话管理
   - files.py: 文件上传下载
   - tasks.py: 任务管理
   - update.py, pack.py, extract.py, crc.py: 各功能路由

3. 业务逻辑
   - session_service.py: 会话 CRUD
   - file_service.py: 文件存储管理
   - task_service.py: 任务创建与状态管理
   - cli_runner.py: CLI 命令执行

4. 过期清理
   - utils/cleanup.py: 清理逻辑
   - FastAPI lifespan 钩子启动定时清理

### 阶段 3：前端开发

1. 项目初始化
   ```bash
   npm create vite@latest frontend -- --template vue
   cd frontend
   npm install pinia vue-router element-plus axios
   ```

2. 核心功能
   - utils/uuid.js: UUID 生成与 localStorage 存储
   - api/: API 封装
   - stores/: Pinia 状态管理

3. 页面开发
   - Home.vue: 首页
   - Update.vue, Pack.vue, Extract.vue, Crc.vue: 功能页面
   - Tasks.vue: 任务列表与状态

4. 组件开发
   - FileUpload.vue: 文件上传组件
   - TaskStatus.vue: 任务状态展示
   - NavBar.vue: 导航栏

### 阶段 4：部署配置

1. Docker 配置
   - Dockerfile.backend
   - Dockerfile.frontend
   - docker-compose.yml

2. Nginx 配置
   - 反向代理 API
   - 静态文件服务

---

## 核心流程

### 用户使用流程

```
1. 用户访问网站
   └── 前端生成 UUID 存入 localStorage

2. 用户上传文件
   └── 文件存储到 storage/uploads/{uuid}/
   └── 数据库创建 File 记录

3. 用户提交任务
   └── 创建 Task 记录 (status: pending)
   └── BackgroundTasks 异步执行 CLI 命令
   └── 更新 Task 状态

4. 用户查询任务
   └── GET /api/tasks/{task_id}
   └── 返回任务状态和结果文件 ID

5. 用户下载结果
   └── GET /api/files/download/{file_id}

6. 24小时后
   └── 定时清理任务删除过期数据
```

### 文件清理流程

```
定时器触发（每小时）
    │
    ▼
查询过期会话 (expires_at < now)
    │
    ▼
遍历每个过期会话
    │
    ├── 删除 storage/uploads/{uuid}/ 目录
    ├── 删除 storage/outputs/{uuid}/ 目录
    └── 删除数据库记录 (级联删除 tasks, files)
    │
    ▼
提交事务，记录日志
```

---

## 同步上游更新

```bash
# 更新上游代码
git submodule update --remote upstream/BA-Modding-Toolkit

# 提交更新
git add upstream/
git commit -m "chore: update upstream BA-Modding-Toolkit"
```

---

## 注意事项

1. **并发安全**: SQLite 写操作需要考虑并发，使用 WAL 模式
2. **文件大小限制**: 配置上传文件大小上限
3. **CLI 超时**: 设置合理的命令执行超时时间
4. **错误处理**: CLI 执行失败时记录详细错误信息
5. **资源限制**: 限制单用户并发任务数
