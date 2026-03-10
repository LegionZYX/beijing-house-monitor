# Railway 部署指南（已修复）

## 问题总结

之前的部署配置存在以下问题：

1. **多进程启动方式不兼容** - `&` 后台进程在 Railway Docker 环境中不稳定
2. **健康检查可能失败** - 启动命令复杂导致健康检查超时
3. **调度器和 Web 服务耦合** - 一个崩溃会影响另一个

## 修复方案

### 1. 简化启动流程
- 创建 `railway_start.py` 统一处理启动逻辑
- Railway 环境只启动 Web 服务
- 调度器建议通过 Railway Cron 单独配置

### 2. 优化 Dockerfile
- 设置 `RAILWAY_ENVIRONMENT` 环境变量
- 使用 `PYTHONUNBUFFERED=1` 确保日志实时输出

### 3. 更新配置文件
- `railway.json` 和 `railway.toml` 使用新的启动命令
- 健康检查超时增加到 60 秒

## 部署步骤

### 1. 提交代码

```bash
cd beijing-house-monitor
git add -A
git commit -m "Fix Railway deployment configuration"
git push origin main
```

### 2. Railway Dashboard 配置

1. 访问 [railway.app](https://railway.app) 登录
2. 进入你的项目
3. 在 **Settings** → **Deploy** 中确认使用 Dockerfile 构建

### 3. 配置环境变量

在 Railway Dashboard → Variables 中添加：

```
# 必需
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=-1001234567890
TELEGRAM_ADMIN_ID=123456789

# Web 认证
WEB_USERNAME=admin
WEB_PASSWORD=your_secure_password
SECRET_KEY=your_random_secret_key

# 可选
FLASK_DEBUG=false
```

### 4. 添加持久化存储

1. 在 Railway Dashboard 点击 **Add** → **Volume**
2. Mount Path: `/app/data`
3. 大小: 1GB（足够本项目使用）

### 5. 配置定时任务（可选）

如果你需要定时运行爬虫，在 Railway Dashboard → **Cron Jobs** 中添加：

- **Schedule**: `0 */6 * * *`（每6小时）
- **Command**: `python src/scheduler.py --run-once`

或者直接在本地/其他服务器运行调度器，只把 Web 仪表盘部署到 Railway。

## 验证部署

部署完成后，访问 Railway 提供的域名：

- **健康检查**: `https://your-project.up.railway.app/health`
- **Web 仪表盘**: `https://your-project.up.railway.app/`

## 故障排查

### 查看日志
```bash
railway login
railway logs -f
```

### 常见问题

#### 1. 服务启动失败
- 检查环境变量是否全部设置
- 查看 Railway Dashboard 的 Deploy Logs

#### 2. 数据库错误
- 确认 Volume 已挂载到 `/app/data`
- 检查 `DATABASE_PATH` 环境变量

#### 3. 健康检查失败
- 确保 `PORT` 环境变量与 Dockerfile 暴露的端口一致
- 检查 `web/app.py` 中的端口绑定逻辑

#### 4. 认证失败
- 确认 `WEB_USERNAME` 和 `WEB_PASSWORD` 已设置
- 使用浏览器隐私模式测试（避免缓存问题）

## 架构说明

```
┌─────────────────────────────────────┐
│           Railway 容器              │
│  ┌───────────────────────────────┐  │
│  │   railway_start.py            │  │
│  │   └── 启动 Flask Web 服务     │  │
│  │       └── port 8080           │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │   Volume: /app/data           │  │
│  │   └── houses.db (SQLite)      │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         ▼
    ┌────────────┐
    │  Railway   │
    │   Cron     │ (可选)
    │ 每6小时运行 │
    │ scheduler  │
    └────────────┘
```

## 免费额度

- Railway 免费版：每月 $5 额度
- 约可运行 500 小时
- 本项目资源占用低，足够使用
