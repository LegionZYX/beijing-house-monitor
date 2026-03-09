# Railway 部署指南

## 快速部署

### 1. 准备代码

确保代码已推送到 GitHub：

```bash
git add -A
git commit -m "Add Railway deployment config"
git push origin main
```

### 2. Railway 部署

#### 方式一：Web 界面（推荐）

1. 访问 [railway.app](https://railway.app)
2. 点击 "New Project" → "Deploy from GitHub repo"
3. 选择你的 GitHub 仓库
4. Railway 会自动识别 `railway.toml` 配置

#### 方式二：CLI

```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录
railway login

# 关联项目
railway link

# 部署
railway up
```

### 3. 配置环境变量

在 Railway Dashboard 的 Variables 页面添加：

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=-1001234567890
TELEGRAM_ADMIN_ID=123456789
WEB_USERNAME=admin
WEB_PASSWORD=your_password
```

### 4. 添加持久化存储

Railway 默认文件系统是临时的，需要添加 Volume：

1. 在 Railway Dashboard 点击 "Add" → "Volume"
2. Mount Path 设置为 `/app/data`
3. 大小选择 1GB（足够用）

### 5. 验证部署

部署完成后，Railway 会提供一个域名：

- Web 仪表盘：`https://your-project.up.railway.app`
- 健康检查：`https://your-project.up.railway.app/health`

## 注意事项

### 免费额度
- Railway 免费版：每月 $5 额度
- 约可运行 500 小时（足够本项目）

### 数据库
- 使用 SQLite 存储在 Volume 中
- 如需迁移到 PostgreSQL，联系我改代码

### 爬虫运行
- 调度器会在后台自动运行
- 每 6 小时爬取一次数据

### 日志查看
```bash
railway logs
```

## 故障排查

### 服务启动失败
检查日志：
```bash
railway logs -f
```

### 数据库权限错误
确保 Volume 已正确挂载到 `/app/data`

### Telegram 通知不工作
检查环境变量是否正确设置，特别是 `TELEGRAM_CHANNEL_ID`
