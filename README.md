# 北京房产监控系统

监控北京二手房和法拍房，支持价格趋势分析和实时推送。

## 功能特性

- **多源数据采集**：链家、贝壳、京东法拍
- **智能筛选**：区域、面积、价格、楼龄、电梯等条件
- **价格趋势**：历史价格曲线、降价提醒
- **法拍房监控**：开拍提醒、折扣分析
- **Web 仪表盘**：可视化数据展示
- **Telegram 推送**：新房源、降价实时通知

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd beijing-house-monitor

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=your_channel_id
TELEGRAM_ADMIN_ID=your_admin_id

# Web 认证
WEB_USERNAME=admin
WEB_PASSWORD=your_password
```

**获取 Telegram Channel ID：**
1. 创建一个新的 Telegram 频道
2. 将 Bot 添加为频道管理员
3. 在频道中发送一条消息
4. 转发该消息给 @userinfobot，获取频道 ID（格式如：-1001234567890）

### 3. 运行

#### 本地运行

```bash
# 启动调度器（后台采集数据）
python src/scheduler.py

# 启动 Web 服务（另一个终端）
python web/app.py
```

#### Docker 部署

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 4. 访问 Web 仪表盘

打开浏览器访问：`http://localhost:8080`

默认账号密码：admin / admin（可在 .env 中修改）

## 项目结构

```
beijing-house-monitor/
├── config/
│   └── config.yaml          # 配置文件
├── src/
│   ├── database.py          # 数据库操作
│   ├── filter_engine.py     # 筛选引擎
│   ├── notifier.py          # 通知推送
│   └── scheduler.py         # 定时任务
├── crawlers/
│   ├── base.py              # 爬虫基类
│   ├── lianjia.py           # 链家爬虫
│   ├── beike.py             # 贝壳爬虫
│   └── jd_auction.py        # 京东法拍爬虫
├── web/
│   ├── app.py               # Flask 应用
│   └── templates/           # HTML 模板
├── data/
│   └── houses.db            # SQLite 数据库
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 配置说明

编辑 `config/config.yaml`：

```yaml
# 默认筛选条件（符合你的需求）
default_filters:
  districts: ["朝阳", "海淀", "东城", "顺义"]
  house_types: ["second_hand", "auction"]
  min_area: 120
  max_price: 500
  max_build_year: 2010  # 楼龄不超过15年
  require_elevator: true

# 爬虫配置
crawlers:
  lianjia:
    enabled: true
    interval_hours: 6
    max_pages: 3
```

## 注意事项

1. **反爬策略**：爬虫已设置随机延迟，请勿频繁抓取
2. **数据准确性**：法拍房信息变化快，以官方为准
3. **换手率估算**：基于挂牌/成交比例估算，仅供参考

## 许可证

MIT
