"""
通知推送模块
支持 Telegram 频道推送
"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime


class Notifier:
    """通知推送器"""
    
    def __init__(self, bot_token: str = None, channel_id: str = None, admin_id: str = None):
        """
        Args:
            bot_token: Telegram Bot Token
            channel_id: 通知频道ID（用于推送房源）
            admin_id: 管理员ID（用于系统通知）
        """
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.admin_id = admin_id
        self._bot = None
    
    async def _get_bot(self):
        """获取 Telegram Bot 实例"""
        if self._bot is None and self.bot_token:
            try:
                from telegram import Bot
                self._bot = Bot(token=self.bot_token)
            except ImportError:
                print("python-telegram-bot not installed")
        return self._bot
    
    def _format_house_message(self, house: Dict) -> str:
        """格式化房源消息"""
        # 法拍房特殊标识
        is_auction = house.get('house_type') == 'auction'
        auction_badge = "🔥【法拍房】" if is_auction else ""
        
        # 基础信息
        title = house.get('title', '未知房源')
        district = house.get('district', '')
        community = house.get('community_name', '')
        area = house.get('area_size', 0)
        total_price = house.get('total_price', 0)
        unit_price = house.get('unit_price', 0)
        rooms = house.get('rooms', 0)
        halls = house.get('halls', 0)
        floor = house.get('floor', 0)
        total_floors = house.get('total_floors', 0)
        build_year = house.get('build_year', '')
        has_elevator = "有" if house.get('has_elevator') else "无"
        
        # 价格显示
        price_text = f"{total_price:.0f}万" if total_price else "价格面议"
        unit_price_text = f"{unit_price:.0f}元/㎡" if unit_price else ""
        
        # 户型显示
        layout = f"{rooms}室{halls}厅" if rooms else ""
        
        # 楼层显示
        floor_text = f"{floor}/{total_floors}层" if floor and total_floors else ""
        
        # 标签
        tags = house.get('tags', [])
        if isinstance(tags, str):
            import json
            try:
                tags = json.loads(tags)
            except:
                tags = []
        tags_text = " | ".join(tags[:5]) if tags else ""
        
        # 法拍房额外信息
        auction_info = ""
        if is_auction:
            starting_price = house.get('starting_price', 0)
            market_price = house.get('market_price', 0)
            deposit = house.get('deposit', 0)
            auction_start = house.get('auction_start_time', '')
            
            if starting_price and market_price:
                discount = (1 - starting_price / market_price) * 100
                auction_info += f"\n💰 起拍价: {starting_price:.0f}万"
                auction_info += f"\n📊 评估价: {market_price:.0f}万"
                auction_info += f"\n🎯 折扣: {discount:.1f}%"
            if deposit:
                auction_info += f"\n💵 保证金: {deposit:.0f}万"
            if auction_start:
                try:
                    from dateutil import parser
                    start_dt = parser.parse(auction_start)
                    now = datetime.now()
                    if start_dt > now:
                        days_left = (start_dt - now).days
                        auction_info += f"\n⏰ 开拍时间: {start_dt.strftime('%m月%d日 %H:%M')} ({days_left}天后)"
                except:
                    auction_info += f"\n⏰ 开拍时间: {auction_start}"
        
        # 组装消息
        message = f"""
{auction_badge} <b>{title}</b>

📍 <b>位置</b>: {district} {community}
💰 <b>总价</b>: {price_text} {unit_price_text}
📐 <b>面积</b>: {area:.0f}㎡ {layout}
🏢 <b>楼层</b>: {floor_text} 电梯:{has_elevator}
📅 <b>建造年份</b>: {build_year}年
{auction_info}

🏷️ <b>标签</b>: {tags_text}

<a href="{house.get('source_url', '#')}">🔗 查看详情</a>
        """.strip()
        
        return message
    
    async def notify_new_house(self, house: Dict, user_id: str = None, channel_id: str = None):
        """
        新房源通知
        
        Args:
            house: 房源数据
            user_id: 私聊用户ID（可选）
            channel_id: 频道ID（可选，优先使用）
        """
        bot = await self._get_bot()
        if not bot:
            print("Bot not configured")
            return
        
        target_id = channel_id or self.channel_id or user_id
        if not target_id:
            print("No target for notification")
            return
        
        message = self._format_house_message(house)
        
        try:
            await bot.send_message(
                chat_id=target_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            print(f"Sent new house notification to {target_id}")
        except Exception as e:
            print(f"Failed to send notification: {e}")
    
    async def notify_price_drop(self, house: Dict, old_price: float, new_price: float,
                                user_id: str = None, channel_id: str = None):
        """
        降价通知
        
        Args:
            house: 房源数据
            old_price: 原价格
            new_price: 新价格
            user_id: 私聊用户ID（可选）
            channel_id: 频道ID（可选）
        """
        bot = await self._get_bot()
        if not bot:
            return
        
        target_id = channel_id or self.channel_id or user_id
        if not target_id:
            return
        
        drop_amount = old_price - new_price
        drop_percent = (drop_amount / old_price) * 100 if old_price else 0
        
        message = f"""
📉 <b>降价提醒</b>

<b>{house.get('title', '未知房源')}</b>

💰 <b>原价</b>: {old_price:.0f}万
💰 <b>现价</b>: {new_price:.0f}万
📉 <b>降幅</b>: {drop_amount:.0f}万 ({drop_percent:.1f}%)

<a href="{house.get('source_url', '#')}">🔗 查看详情</a>
        """.strip()
        
        try:
            await bot.send_message(
                chat_id=target_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Failed to send price drop notification: {e}")
    
    async def send_daily_summary(self, stats: Dict, user_id: str = None, channel_id: str = None):
        """
        发送每日汇总
        
        Args:
            stats: 统计数据
            user_id: 私聊用户ID（可选）
            channel_id: 频道ID（可选）
        """
        bot = await self._get_bot()
        if not bot:
            return
        
        target_id = channel_id or self.channel_id or user_id
        if not target_id:
            return
        
        today = datetime.now().strftime("%Y年%m月%d日")
        
        message = f"""
📊 <b>北京房产监控日报 - {today}</b>

🏠 <b>今日新增</b>: {stats.get('today_new', 0)} 套
📈 <b>总房源数</b>: {stats.get('total_houses', 0)} 套
🔥 <b>法拍房</b>: {stats.get('auction_count', 0)} 套

<b>区域分布</b>:
"""
        
        district_dist = stats.get('district_distribution', {})
        for district, count in sorted(district_dist.items(), key=lambda x: x[1], reverse=True):
            message += f"• {district}: {count}套\n"
        
        message += "\n继续监控中... 🔍"
        
        try:
            await bot.send_message(
                chat_id=target_id,
                text=message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Failed to send daily summary: {e}")
    
    async def send_system_notification(self, message: str):
        """
        发送系统通知（给管理员）
        """
        if not self.admin_id:
            return
        
        bot = await self._get_bot()
        if not bot:
            return
        
        try:
            await bot.send_message(
                chat_id=self.admin_id,
                text=f"⚙️ <b>系统通知</b>\n\n{message}",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Failed to send system notification: {e}")
    
    # 同步包装方法（方便非异步代码调用）
    def notify_new_house_sync(self, house: Dict, user_id: str = None, channel_id: str = None):
        """同步方式发送新房源通知"""
        try:
            asyncio.run(self.notify_new_house(house, user_id, channel_id))
        except Exception as e:
            print(f"Sync notification failed: {e}")
    
    def notify_price_drop_sync(self, house: Dict, old_price: float, new_price: float,
                               user_id: str = None, channel_id: str = None):
        """同步方式发送降价通知"""
        try:
            asyncio.run(self.notify_price_drop(house, old_price, new_price, user_id, channel_id))
        except Exception as e:
            print(f"Sync notification failed: {e}")
