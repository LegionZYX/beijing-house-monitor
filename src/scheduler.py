"""
定时任务调度器
"""
import os
import sys
import time
import yaml
import schedule
from datetime import datetime
from typing import Dict, List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import Database
from src.filter_engine import FilterEngine
from src.notifier import Notifier
from crawlers import CRAWLERS


class HouseMonitorScheduler:
    """房产监控调度器"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self.db = Database(self.config.get('system', {}).get('database_path', 'data/houses.db'))
        self.filter_engine = FilterEngine(self.config.get('default_filters', {}))
        
        # 初始化通知器
        telegram_config = self.config.get('notifications', {}).get('telegram', {})
        self.notifier = Notifier(
            bot_token=os.environ.get('TELEGRAM_BOT_TOKEN') or telegram_config.get('bot_token'),
            channel_id=os.environ.get('TELEGRAM_CHANNEL_ID') or telegram_config.get('notification_channel_id'),
            admin_id=os.environ.get('TELEGRAM_ADMIN_ID') or telegram_config.get('admin_chat_id')
        )
        
        # 已通知的房源ID（避免重复通知）
        self.notified_houses = set()
    
    def _load_config(self, path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to load config from {path}: {e}")
            return {}
    
    def run_crawler(self, crawler_name: str):
        """运行指定爬虫"""
        print(f"\n[{datetime.now().isoformat()}] Running crawler: {crawler_name}")
        
        crawler_class = CRAWLERS.get(crawler_name)
        if not crawler_class:
            print(f"Unknown crawler: {crawler_name}")
            return
        
        crawler_config = self.config.get('crawlers', {}).get(crawler_name, {})
        if not crawler_config.get('enabled', True):
            print(f"Crawler {crawler_name} is disabled")
            return
        
        started_at = datetime.now().isoformat()
        houses_found = 0
        houses_new = 0
        houses_updated = 0
        
        try:
            crawler = crawler_class()
            
            # 获取爬取参数
            kwargs = {}
            if 'districts' in crawler_config:
                kwargs['districts'] = crawler_config['districts']
            if 'max_pages' in crawler_config:
                kwargs['max_pages'] = crawler_config['max_pages']
            
            # 执行爬取
            houses = crawler.crawl(**kwargs)
            houses_found = len(houses)
            
            print(f"  Found {houses_found} houses")
            
            # 保存到数据库
            for house in houses:
                try:
                    house_id = self.db.save_house(house)
                    
                    # 检查是否是新房源
                    with self.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT first_seen_at FROM houses WHERE id = ?",
                            (house_id,)
                        )
                        row = cursor.fetchone()
                        if row and row[0].startswith(datetime.now().strftime('%Y-%m-%d')):
                            houses_new += 1
                            
                            # 检查是否符合用户筛选条件
                            if self.filter_engine.match(house):
                                score = self.filter_engine.calculate_match_score(house)
                                if score >= 60:  # 匹配度大于60分才通知
                                    self._notify_new_house(house, score)
                        else:
                            houses_updated += 1
                            
                except Exception as e:
                    print(f"  Error saving house: {e}")
            
            # 记录日志
            self.db.log_crawl(
                source=crawler_name,
                status='success',
                houses_found=houses_found,
                houses_new=houses_new,
                houses_updated=houses_updated,
                started_at=started_at
            )
            
            print(f"  Saved: {houses_new} new, {houses_updated} updated")
            
        except Exception as e:
            print(f"  Crawler failed: {e}")
            self.db.log_crawl(
                source=crawler_name,
                status='failed',
                houses_found=houses_found,
                error_message=str(e),
                started_at=started_at
            )
    
    def _notify_new_house(self, house: Dict, score: float):
        """通知新房源"""
        house_key = f"{house.get('source')}:{house.get('source_id')}"
        if house_key in self.notified_houses:
            return
        
        self.notified_houses.add(house_key)
        
        # 添加匹配度信息
        house['match_score'] = score
        
        # 发送通知
        import asyncio
        try:
            asyncio.run(self.notifier.notify_new_house(house))
            print(f"    📧 Notified: {house.get('title', '')[:30]}... (score: {score:.1f})")
        except Exception as e:
            print(f"    Failed to notify: {e}")
    
    def check_price_drops(self):
        """检查降价房源"""
        print(f"\n[{datetime.now().isoformat()}] Checking price drops...")
        
        threshold = self.config.get('price_monitor', {}).get('drop_threshold', 0.05)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 查找最近7天内有价格变动的房源
            cursor.execute("""
                SELECT h.*, MIN(ph.price) as old_price
                FROM houses h
                JOIN price_history ph ON h.id = ph.house_id
                WHERE h.is_deleted = FALSE
                AND ph.recorded_at >= datetime('now', '-7 days')
                AND ph.price_type = 'listing'
                GROUP BY h.id
                HAVING h.total_price < old_price * (1 - ?)
            """, (threshold,))
            
            rows = cursor.fetchall()
            
            for row in rows:
                house = dict(row)
                old_price = house.pop('old_price')
                new_price = house['total_price']
                drop_percent = (old_price - new_price) / old_price * 100
                
                print(f"  💰 Price drop: {house.get('title', '')[:30]}... ({drop_percent:.1f}%)")
                
                # 发送降价通知
                import asyncio
                try:
                    asyncio.run(self.notifier.notify_price_drop(house, old_price, new_price))
                except Exception as e:
                    print(f"    Failed to notify: {e}")
    
    def send_daily_summary(self):
        """发送每日汇总"""
        print(f"\n[{datetime.now().isoformat()}] Sending daily summary...")
        
        stats = self.db.get_stats()
        
        import asyncio
        try:
            asyncio.run(self.notifier.send_daily_summary(stats))
            print("  Daily summary sent")
        except Exception as e:
            print(f"  Failed to send summary: {e}")
    
    def setup_schedule(self):
        """设置定时任务"""
        crawlers_config = self.config.get('crawlers', {})
        
        for crawler_name, crawler_config in crawlers_config.items():
            if not crawler_config.get('enabled', True):
                continue
            
            interval = crawler_config.get('interval_hours', 6)
            
            # 使用闭包捕获 crawler_name
            def make_job(name):
                return lambda: self.run_crawler(name)
            
            schedule.every(interval).hours.do(make_job(crawler_name))
            print(f"Scheduled {crawler_name} every {interval} hours")
        
        # 价格监控
        price_check_interval = self.config.get('price_monitor', {}).get('check_interval', 6)
        schedule.every(price_check_interval).hours.do(self.check_price_drops)
        print(f"Scheduled price check every {price_check_interval} hours")
        
        # 每日汇总（早上9点）
        schedule.every().day.at("09:00").do(self.send_daily_summary)
        print("Scheduled daily summary at 09:00")
    
    def run(self):
        """运行调度器"""
        print("=" * 50)
        print("北京房产监控系统启动")
        print("=" * 50)
        
        # 立即执行一次所有爬虫
        print("\n首次运行，执行所有爬虫...")
        for crawler_name in self.config.get('crawlers', {}).keys():
            self.run_crawler(crawler_name)
        
        # 设置定时任务
        self.setup_schedule()
        
        print("\n调度器运行中...")
        print("按 Ctrl+C 停止")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


def main():
    """主函数"""
    scheduler = HouseMonitorScheduler()
    
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print("\n\n停止调度器")


if __name__ == '__main__':
    main()
