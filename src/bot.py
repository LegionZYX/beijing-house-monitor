"""
Telegram Bot 交互模块
处理用户命令和消息
"""
import os
import sys
import logging
from typing import Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler
)

from src.database import Database
from src.filter_engine import FilterEngine

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 对话状态
SET_DISTRICT, SET_PRICE, SET_AREA = range(3)


class HouseMonitorBot:
    """房产监控 Telegram Bot"""
    
    def __init__(self, token: str = None):
        self.token = token or os.environ.get('TELEGRAM_BOT_TOKEN')
        self.db = Database()
        self.filter_engine = FilterEngine()
        self.application = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        user = update.effective_user
        
        welcome_text = f"""
👋 你好 {user.first_name}！

欢迎使用北京房产监控系统！

我可以帮你：
🔍 监控北京二手房和法拍房
📊 分析价格趋势
📉 降价提醒
📱 实时推送符合条件的房源

使用 /help 查看所有命令
        """
        
        await update.message.reply_text(welcome_text)
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        help_text = """
📋 可用命令：

/start - 开始使用
/help - 显示帮助
/status - 查看系统状态
/filters - 查看当前筛选条件
/setfilter - 设置筛选条件
/auctions - 查看法拍房
/stats - 查看统计数据
/latest - 查看最新房源
/price <房源ID> - 查看价格趋势

💡 提示：
筛选条件会自动保存，符合要求的新房源会推送到频道。
        """
        
        await update.message.reply_text(help_text)
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /status 命令"""
        stats = self.db.get_stats()
        
        status_text = f"""
📊 系统状态

🏠 总房源数：{stats['total_houses']} 套
📈 今日新增：{stats['today_new']} 套
🔥 法拍房：{stats['auction_count']} 套

📍 区域分布：
"""
        
        for district, count in sorted(stats['district_distribution'].items(), 
                                      key=lambda x: x[1], reverse=True):
            status_text += f"  • {district}：{count} 套\n"
        
        await update.message.reply_text(status_text)
    
    async def filters(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /filters 命令"""
        filters = self.filter_engine.filters
        
        filters_text = f"""
🔍 当前筛选条件

📍 区域：{', '.join(filters.get('districts', []))}
🏠 类型：{', '.join(filters.get('house_types', ['二手房', '法拍房']))}
📐 面积：≥{filters.get('min_area', 0)}㎡
💰 价格：≤{filters.get('max_price', 0)}万
📅 楼龄：≤{2026 - filters.get('max_build_year', 2000)}年
🛗 电梯：{'必须有' if filters.get('require_elevator') else '不限'}

使用 /setfilter 修改筛选条件
        """
        
        await update.message.reply_text(filters_text)
    
    async def setfilter_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """开始设置筛选条件"""
        keyboard = [
            [InlineKeyboardButton("朝阳", callback_data='district_朝阳'),
             InlineKeyboardButton("海淀", callback_data='district_海淀')],
            [InlineKeyboardButton("东城", callback_data='district_东城'),
             InlineKeyboardButton("顺义", callback_data='district_顺义')],
            [InlineKeyboardButton("完成设置", callback_data='filter_done')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "请选择要监控的区域（可多选）：",
            reply_markup=reply_markup
        )
        
        return SET_DISTRICT
    
    async def setfilter_district(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理区域选择"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == 'filter_done':
            # 进入价格设置
            await query.edit_message_text(
                "请输入最高预算（万元），例如：500"
            )
            return SET_PRICE
        
        # 处理区域选择
        district = data.replace('district_', '')
        
        # 保存到用户数据
        if 'districts' not in context.user_data:
            context.user_data['districts'] = []
        
        if district in context.user_data['districts']:
            context.user_data['districts'].remove(district)
        else:
            context.user_data['districts'].append(district)
        
        # 更新键盘
        keyboard = []
        districts = ['朝阳', '海淀', '东城', '顺义', '丰台', '昌平', '大兴']
        row = []
        for d in districts:
            prefix = "✅ " if d in context.user_data['districts'] else ""
            row.append(InlineKeyboardButton(f"{prefix}{d}", callback_data=f'district_{d}'))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("完成设置", callback_data='filter_done')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"已选择：{', '.join(context.user_data['districts']) or '无'}\n\n请选择要监控的区域：",
            reply_markup=reply_markup
        )
        
        return SET_DISTRICT
    
    async def setfilter_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理价格输入"""
        try:
            max_price = float(update.message.text)
            context.user_data['max_price'] = max_price
            
            await update.message.reply_text(
                f"最高预算设置为：{max_price}万\n\n请输入最小面积（平米），例如：120"
            )
            return SET_AREA
            
        except ValueError:
            await update.message.reply_text(
                "请输入有效的数字，例如：500"
            )
            return SET_PRICE
    
    async def setfilter_area(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理面积输入，完成设置"""
        try:
            min_area = float(update.message.text)
            context.user_data['min_area'] = min_area
            
            # 保存筛选条件
            new_filters = {
                'districts': context.user_data.get('districts', ['朝阳', '海淀', '东城', '顺义']),
                'max_price': context.user_data.get('max_price', 500),
                'min_area': min_area,
                'house_types': ['second_hand', 'auction'],
                'require_elevator': True,
                'max_build_year': 2010
            }
            
            self.filter_engine.update_filters(new_filters)
            
            # 保存到数据库（用户订阅）
            user_id = str(update.effective_user.id)
            import json
            self._save_user_filter(user_id, new_filters)
            
            await update.message.reply_text(
                f"""
✅ 筛选条件已保存！

📍 区域：{', '.join(new_filters['districts'])}
💰 最高预算：{new_filters['max_price']}万
📐 最小面积：{new_filters['min_area']}㎡
🛗 必须有电梯
📅 楼龄不超过15年

符合这些条件的新房源会推送到频道。
                """
            )
            
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "请输入有效的数字，例如：120"
            )
            return SET_AREA
    
    def _save_user_filter(self, user_id: str, filters: Dict):
        """保存用户筛选条件到数据库"""
        import json
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查是否已存在
            cursor.execute(
                "SELECT id FROM user_subscriptions WHERE user_id = ?",
                (user_id,)
            )
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute(
                    "UPDATE user_subscriptions SET filters = ? WHERE user_id = ?",
                    (json.dumps(filters, ensure_ascii=False), user_id)
                )
            else:
                cursor.execute(
                    "INSERT INTO user_subscriptions (user_id, filters) VALUES (?, ?)",
                    (user_id, json.dumps(filters, ensure_ascii=False))
                )
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """取消设置"""
        await update.message.reply_text(
            "已取消设置筛选条件。"
        )
        return ConversationHandler.END
    
    async def auctions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /auctions 命令"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取即将开始的法拍房
            cursor.execute("""
                SELECT * FROM houses
                WHERE house_type = 'auction'
                AND auction_status = 'upcoming'
                AND is_deleted = FALSE
                ORDER BY auction_start_time ASC
                LIMIT 10
            """)
            
            auctions = [dict(row) for row in cursor.fetchall()]
        
        if not auctions:
            await update.message.reply_text("暂无即将开始的法拍房。")
            return
        
        text = "🔥 即将开始的法拍房\n\n"
        
        for i, auction in enumerate(auctions[:5], 1):
            title = auction.get('title', '未知')[:30]
            starting_price = auction.get('starting_price', 0)
            market_price = auction.get('market_price', 0)
            
            discount = ""
            if starting_price and market_price:
                discount_pct = (1 - starting_price / market_price) * 100
                discount = f"（{discount_pct:.1f}%折扣）"
            
            text += f"{i}. {title}...\n"
            text += f"   起拍价：{starting_price}万 {discount}\n"
            text += f"   [查看详情]({auction.get('source_url', '#')})\n\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def latest(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /latest 命令"""
        houses = self.db.get_houses(limit=10)
        
        if not houses:
            await update.message.reply_text("暂无房源数据。")
            return
        
        text = "📋 最新房源\n\n"
        
        for i, house in enumerate(houses, 1):
            title = house.get('title', '未知')[:25]
            price = house.get('total_price', 0)
            area = house.get('area_size', 0)
            district = house.get('district', '')
            
            house_type = "🔥" if house.get('house_type') == 'auction' else "🏠"
            
            text += f"{i}. {house_type} {title}...\n"
            text += f"   {district} | {price}万 | {area}㎡\n"
            text += f"   /price_{house.get('id')} 查看趋势\n\n"
        
        await update.message.reply_text(text)
    
    async def price_trend(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理价格趋势查询"""
        # 从命令中提取房源ID
        text = update.message.text
        
        # 支持 /price_123 或 /price 123
        if '_' in text:
            try:
                house_id = int(text.split('_')[1])
            except (IndexError, ValueError):
                await update.message.reply_text("请使用格式：/price_房源ID 或 /price 房源ID")
                return
        else:
            args = context.args
            if not args:
                await update.message.reply_text("请提供房源ID，例如：/price 123")
                return
            try:
                house_id = int(args[0])
            except ValueError:
                await update.message.reply_text("房源ID必须是数字。")
                return
        
        # 获取房源信息
        house = self.db.get_house_by_id(house_id)
        if not house:
            await update.message.reply_text("未找到该房源。")
            return
        
        # 获取价格趋势
        from src.price_analyzer import PriceAnalyzer
        analyzer = PriceAnalyzer(self.db)
        trend = analyzer.get_price_trend(house_id)
        
        if not trend:
            await update.message.reply_text("暂无价格趋势数据。")
            return
        
        # 格式化输出
        trend_emoji = {"up": "📈", "down": "📉", "stable": "➡️"}
        trend_text = {"up": "上涨", "down": "下跌", "stable": "平稳"}
        
        text = f"""
📊 {house.get('title', '未知房源')[:30]}...

💰 当前价格：{trend['current_price']}万
📈 7天变动：{trend['change_7d']}%
📈 30天变动：{trend['change_30d']}%
📈 90天变动：{trend['change_90d']}%

趋势：{trend_emoji.get(trend['trend'], '')} {trend_text.get(trend['trend'], '未知')}

历史最高：{trend['max_price']}万
历史最低：{trend['min_price']}万
        """
        
        await update.message.reply_text(text)
    
    def setup_handlers(self):
        """设置命令处理器"""
        self.application = Application.builder().token(self.token).build()
        
        # 基础命令
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("filters", self.filters))
        self.application.add_handler(CommandHandler("auctions", self.auctions))
        self.application.add_handler(CommandHandler("latest", self.latest))
        self.application.add_handler(CommandHandler("price", self.price_trend))
        
        # 设置筛选条件的对话处理器
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("setfilter", self.setfilter_start)],
            states={
                SET_DISTRICT: [CallbackQueryHandler(self.setfilter_district)],
                SET_PRICE: [CommandHandler("cancel", self.cancel)],
                SET_AREA: [CommandHandler("cancel", self.cancel)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        self.application.add_handler(conv_handler)
        
        # 价格趋势快捷命令
        self.application.add_handler(CommandHandler("price", self.price_trend))
    
    def run(self):
        """运行 Bot"""
        if not self.token:
            logger.error("Telegram Bot Token not configured")
            return
        
        self.setup_handlers()
        
        logger.info("Starting Telegram Bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """主函数"""
    bot = HouseMonitorBot()
    bot.run()


if __name__ == '__main__':
    main()
