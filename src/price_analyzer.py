"""
价格分析器
提供价格趋势分析、降价检测等功能
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics


class PriceAnalyzer:
    """价格趋势分析器"""
    
    def __init__(self, database):
        """
        Args:
            database: Database 实例
        """
        self.db = database
    
    def get_price_trend(self, house_id: int, days: int = 90) -> Dict:
        """
        获取指定房源的价格趋势
        
        Args:
            house_id: 房源ID
            days: 查询天数
            
        Returns:
            {
                "current_price": float,
                "price_history": List[{"date": str, "price": float}],
                "change_7d": float,    # 7天变动百分比
                "change_30d": float,   # 30天变动百分比
                "change_90d": float,   # 90天变动百分比
                "trend": str,          # "up", "down", "stable"
                "avg_price": float,    # 平均价格
                "min_price": float,    # 最低价格
                "max_price": float     # 最高价格
            }
        """
        # 获取当前价格
        house = self.db.get_house_by_id(house_id)
        if not house:
            return None
        
        current_price = house.get('total_price')
        
        # 获取价格历史
        price_history = self.db.get_price_history(house_id, days=days)
        
        if not price_history or len(price_history) < 2:
            return {
                "current_price": current_price,
                "price_history": [],
                "change_7d": 0,
                "change_30d": 0,
                "change_90d": 0,
                "trend": "stable",
                "avg_price": current_price,
                "min_price": current_price,
                "max_price": current_price
            }
        
        # 格式化价格历史
        formatted_history = []
        prices = []
        
        for record in price_history:
            price = record.get('price')
            date = record.get('recorded_at', '')
            if price and date:
                formatted_history.append({
                    "date": date[:10],  # 只取日期部分
                    "price": float(price)
                })
                prices.append(float(price))
        
        # 计算价格变动
        change_7d = self._calculate_change(price_history, 7)
        change_30d = self._calculate_change(price_history, 30)
        change_90d = self._calculate_change(price_history, 90)
        
        # 判断趋势
        trend = self._determine_trend(change_7d, change_30d)
        
        return {
            "current_price": current_price,
            "price_history": formatted_history,
            "change_7d": round(change_7d * 100, 2),
            "change_30d": round(change_30d * 100, 2),
            "change_90d": round(change_90d * 100, 2),
            "trend": trend,
            "avg_price": round(statistics.mean(prices), 2) if prices else current_price,
            "min_price": min(prices) if prices else current_price,
            "max_price": max(prices) if prices else current_price
        }
    
    def _calculate_change(self, price_history: List[Dict], days: int) -> float:
        """
        计算价格变动百分比
        
        Args:
            price_history: 价格历史列表
            days: 天数
            
        Returns:
            变动百分比（小数形式，如 0.05 表示上涨5%）
        """
        if not price_history:
            return 0
        
        # 获取当前价格（最新的记录）
        current_record = price_history[-1]
        current_price = current_record.get('price')
        
        if not current_price:
            return 0
        
        # 查找N天前的价格
        cutoff_date = datetime.now() - timedelta(days=days)
        old_price = None
        
        for record in reversed(price_history[:-1]):  # 倒序遍历，排除最新
            recorded_at = record.get('recorded_at', '')
            try:
                record_date = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
                if record_date <= cutoff_date:
                    old_price = record.get('price')
                    break
            except:
                continue
        
        # 如果没找到N天前的记录，使用最早的记录
        if old_price is None and len(price_history) > 1:
            old_price = price_history[0].get('price')
        
        if old_price and old_price > 0:
            return (current_price - old_price) / old_price
        
        return 0
    
    def _determine_trend(self, change_7d: float, change_30d: float) -> str:
        """
        判断价格趋势
        
        Args:
            change_7d: 7天变动
            change_30d: 30天变动
            
        Returns:
            "up" | "down" | "stable"
        """
        threshold = 0.02  # 2%阈值
        
        # 综合判断
        avg_change = (change_7d + change_30d) / 2
        
        if avg_change > threshold:
            return "up"
        elif avg_change < -threshold:
            return "down"
        else:
            return "stable"
    
    def get_community_trend(self, community_name: str, district: str, days: int = 90) -> Dict:
        """
        获取小区整体价格趋势
        
        Args:
            community_name: 小区名称
            district: 区域
            days: 查询天数
            
        Returns:
            小区价格趋势数据
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取小区内所有房源
            cursor.execute("""
                SELECT id, total_price, unit_price, area_size, first_seen_at
                FROM houses
                WHERE community_name = ? AND district = ?
                AND is_deleted = FALSE
                AND total_price IS NOT NULL
            """, (community_name, district))
            
            houses = [dict(row) for row in cursor.fetchall()]
        
        if not houses:
            return None
        
        # 计算统计信息
        prices = [h['total_price'] for h in houses if h.get('total_price')]
        unit_prices = [h['unit_price'] for h in houses if h.get('unit_price')]
        areas = [h['area_size'] for h in houses if h.get('area_size')]
        
        if not prices:
            return None
        
        # 获取小区统计数据
        stats = self.db.get_community_stats(community_name, district)
        
        result = {
            "community_name": community_name,
            "district": district,
            "listing_count": len(houses),
            "avg_price": round(statistics.mean(prices), 2),
            "median_price": round(statistics.median(prices), 2),
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_unit_price": round(statistics.mean(unit_prices), 2) if unit_prices else None,
            "avg_area": round(statistics.mean(areas), 2) if areas else None,
        }
        
        if stats:
            result.update({
                "price_change_30d": stats.get('price_change_30d'),
                "price_change_90d": stats.get('price_change_90d'),
                "turnover_rate": stats.get('turnover_rate')
            })
        
        return result
    
    def detect_price_drops(self, threshold: float = 0.05, days: int = 7) -> List[Dict]:
        """
        检测降价房源
        
        Args:
            threshold: 降价幅度阈值（默认5%）
            days: 检查天数范围
            
        Returns:
            降价房源列表
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 查找最近有价格变动的房源
            cursor.execute("""
                SELECT h.*, MIN(ph.price) as old_price, MAX(ph.price) as peak_price
                FROM houses h
                JOIN price_history ph ON h.id = ph.house_id
                WHERE h.is_deleted = FALSE
                AND ph.recorded_at >= datetime('now', '-{} days')
                AND ph.price_type = 'listing'
                GROUP BY h.id
                HAVING h.total_price < peak_price * (1 - ?)
                ORDER BY (peak_price - h.total_price) / peak_price DESC
            """.format(days), (threshold,))
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                house = dict(row)
                old_price = house.pop('old_price')
                peak_price = house.pop('peak_price')
                current_price = house['total_price']
                
                drop_amount = peak_price - current_price
                drop_percent = (drop_amount / peak_price) * 100 if peak_price else 0
                
                house['price_drop'] = {
                    "old_price": peak_price,
                    "new_price": current_price,
                    "drop_amount": round(drop_amount, 2),
                    "drop_percent": round(drop_percent, 2)
                }
                
                results.append(house)
            
            return results
    
    def get_district_comparison(self) -> List[Dict]:
        """
        获取各区域价格对比
        
        Returns:
            区域价格对比数据
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    district,
                    COUNT(*) as listing_count,
                    AVG(total_price) as avg_price,
                    AVG(unit_price) as avg_unit_price,
                    MIN(total_price) as min_price,
                    MAX(total_price) as max_price,
                    AVG(area_size) as avg_area
                FROM houses
                WHERE is_deleted = FALSE
                AND total_price IS NOT NULL
                AND unit_price IS NOT NULL
                GROUP BY district
                ORDER BY avg_unit_price DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "district": row[0],
                    "listing_count": row[1],
                    "avg_price": round(row[2], 2) if row[2] else None,
                    "avg_unit_price": round(row[3], 2) if row[3] else None,
                    "min_price": row[4],
                    "max_price": row[5],
                    "avg_area": round(row[6], 2) if row[6] else None
                })
            
            return results
    
    def get_price_distribution(self, district: str = None) -> Dict:
        """
        获取价格分布
        
        Args:
            district: 区域（可选，None表示全部）
            
        Returns:
            价格区间分布
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT total_price
                FROM houses
                WHERE is_deleted = FALSE
                AND total_price IS NOT NULL
            """
            params = []
            
            if district:
                query += " AND district = ?"
                params.append(district)
            
            cursor.execute(query, params)
            prices = [row[0] for row in cursor.fetchall()]
        
        if not prices:
            return {}
        
        # 定义价格区间
        ranges = [
            (0, 300, "300万以下"),
            (300, 500, "300-500万"),
            (500, 800, "500-800万"),
            (800, 1000, "800-1000万"),
            (1000, 1500, "1000-1500万"),
            (1500, float('inf'), "1500万以上")
        ]
        
        distribution = {}
        for min_p, max_p, label in ranges:
            count = sum(1 for p in prices if min_p <= p < max_p)
            distribution[label] = {
                "count": count,
                "percent": round(count / len(prices) * 100, 1)
            }
        
        return distribution
