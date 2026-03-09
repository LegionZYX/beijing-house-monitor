"""
换手率估算器
计算小区换手率、活跃度等指标
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import statistics


class TurnoverCalculator:
    """
    小区换手率估算器
    
    换手率 = 一定时期内的成交量 / 总户数
    
    由于无法获取准确的总户数，采用以下估算方法:
    1. 基于挂牌量和成交量的比例估算
    2. 参考同区域类似小区的已知数据
    """
    
    # 估算参数
    AVG_LISTING_PERIOD_DAYS = 90  # 平均挂牌周期（天）
    DEAL_TO_LISTING_RATIO = 0.3   # 成交占挂牌比例（经验值）
    
    def __init__(self, database):
        """
        Args:
            database: Database 实例
        """
        self.db = database
    
    def calculate_turnover_rate(self, community_name: str, district: str) -> Dict:
        """
        估算小区年化换手率
        
        Args:
            community_name: 小区名称
            district: 区域
            
        Returns:
            {
                "turnover_rate": float,      # 年化换手率（百分比）
                "confidence": str,           # 置信度: high/medium/low
                "method": str,               # 计算方法
                "listing_count": int,        # 当前挂牌数
                "estimated_deals_annual": float,  # 估算年成交量
                "estimated_total_units": int     # 估算总户数
            }
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取小区内房源
            cursor.execute("""
                SELECT id, total_price, unit_price, area_size, first_seen_at, last_seen_at
                FROM houses
                WHERE community_name = ? AND district = ?
                AND is_deleted = FALSE
            """, (community_name, district))
            
            houses = [dict(row) for row in cursor.fetchall()]
        
        if not houses:
            return None
        
        listing_count = len(houses)
        
        # 方法1: 基于挂牌周期估算
        # 假设：平均挂牌90天，则年换手率 ≈ 当前挂牌数 / 总户数 * (365/90)
        # 反推：总户数 ≈ 当前挂牌数 * (365/90) / 换手率
        # 假设正常换手率3%，则总户数 ≈ 当前挂牌数 * 135
        
        estimated_total_units = int(listing_count * 135)
        
        # 估算年成交量
        # 假设30%的挂牌最终成交
        estimated_deals_annual = listing_count * (365 / self.AVG_LISTING_PERIOD_DAYS) * self.DEAL_TO_LISTING_RATIO
        
        # 计算换手率
        turnover_rate = (estimated_deals_annual / estimated_total_units) * 100
        
        # 限制在合理范围内（1%-10%）
        turnover_rate = max(1.0, min(10.0, turnover_rate))
        
        return {
            "turnover_rate": round(turnover_rate, 2),
            "confidence": "medium",
            "method": "listing_based",
            "listing_count": listing_count,
            "estimated_deals_annual": round(estimated_deals_annual, 1),
            "estimated_total_units": estimated_total_units
        }
    
    def get_community_activity_level(self, community_name: str, district: str) -> str:
        """
        获取小区活跃度等级
        
        Args:
            community_name: 小区名称
            district: 区域
            
        Returns:
            "high" | "medium" | "low"
        """
        result = self.calculate_turnover_rate(community_name, district)
        if not result:
            return "unknown"
        
        rate = result.get('turnover_rate', 0)
        listing_count = result.get('listing_count', 0)
        
        # 综合换手率和挂牌数判断
        if rate >= 4.0 or listing_count >= 20:
            return "high"
        elif rate >= 2.0 or listing_count >= 10:
            return "medium"
        else:
            return "low"
    
    def calculate_all_communities(self, district: str = None) -> List[Dict]:
        """
        计算所有小区的换手率
        
        Args:
            district: 区域（可选）
            
        Returns:
            小区换手率列表
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT community_name, district, COUNT(*) as listing_count
                FROM houses
                WHERE community_name IS NOT NULL
                AND is_deleted = FALSE
            """
            params = []
            
            if district:
                query += " AND district = ?"
                params.append(district)
            
            query += " GROUP BY community_name, district HAVING listing_count >= 3"
            query += " ORDER BY listing_count DESC"
            
            cursor.execute(query, params)
            communities = cursor.fetchall()
        
        results = []
        for row in communities:
            community_name, district, listing_count = row
            
            turnover_data = self.calculate_turnover_rate(community_name, district)
            if turnover_data:
                # 获取小区统计信息
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT AVG(total_price), AVG(unit_price), AVG(area_size)
                        FROM houses
                        WHERE community_name = ? AND district = ?
                        AND is_deleted = FALSE
                    """, (community_name, district))
                    
                    stats_row = cursor.fetchone()
                    if stats_row:
                        turnover_data.update({
                            "avg_price": round(stats_row[0], 2) if stats_row[0] else None,
                            "avg_unit_price": round(stats_row[1], 2) if stats_row[1] else None,
                            "avg_area": round(stats_row[2], 2) if stats_row[2] else None
                        })
                
                turnover_data['community_name'] = community_name
                turnover_data['district'] = district
                turnover_data['activity_level'] = self.get_community_activity_level(
                    community_name, district
                )
                
                results.append(turnover_data)
        
        return results
    
    def get_market_heat_index(self, district: str = None) -> Dict:
        """
        获取市场热度指数
        
        综合指标：
        - 新增挂牌速度
        - 成交周期
        - 价格变动趋势
        - 换手率
        
        Args:
            district: 区域（可选）
            
        Returns:
            市场热度数据
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 基础查询条件
            district_filter = "AND district = ?" if district else ""
            params = [district] if district else []
            
            # 近30天新增房源数
            cursor.execute(f"""
                SELECT COUNT(*) FROM houses
                WHERE first_seen_at >= datetime('now', '-30 days')
                AND is_deleted = FALSE
                {district_filter}
            """, params)
            new_listings_30d = cursor.fetchone()[0]
            
            # 总房源数
            cursor.execute(f"""
                SELECT COUNT(*) FROM houses
                WHERE is_deleted = FALSE
                {district_filter}
            """, params)
            total_listings = cursor.fetchone()[0]
            
            # 法拍房数量
            cursor.execute(f"""
                SELECT COUNT(*) FROM houses
                WHERE house_type = 'auction'
                AND is_deleted = FALSE
                {district_filter}
            """, params)
            auction_count = cursor.fetchone()[0]
            
            # 平均价格
            cursor.execute(f"""
                SELECT AVG(unit_price) FROM houses
                WHERE unit_price IS NOT NULL
                AND is_deleted = FALSE
                {district_filter}
            """, params)
            avg_unit_price = cursor.fetchone()[0]
        
        # 计算热度指数 (0-100)
        # 基于：新增挂牌速度、法拍房占比、平均价格水平
        
        # 新增挂牌速度得分 (0-40)
        if total_listings > 0:
            new_ratio = new_listings_30d / total_listings
            new_listing_score = min(40, new_ratio * 200)  # 每月新增15%得满分
        else:
            new_listing_score = 0
        
        # 法拍房活跃度得分 (0-30)
        if total_listings > 0:
            auction_ratio = auction_count / total_listings
            auction_score = min(30, auction_ratio * 300)  # 法拍房占比10%得满分
        else:
            auction_score = 0
        
        # 价格水平得分 (0-30)
        # 基于平均单价，假设北京平均6万/平
        if avg_unit_price:
            price_score = min(30, avg_unit_price / 60000 * 30)
        else:
            price_score = 15
        
        heat_index = new_listing_score + auction_score + price_score
        
        # 确定热度等级
        if heat_index >= 70:
            heat_level = "hot"
            heat_desc = "市场活跃"
        elif heat_index >= 40:
            heat_level = "warm"
            heat_desc = "市场平稳"
        else:
            heat_level = "cold"
            heat_desc = "市场冷清"
        
        return {
            "heat_index": round(heat_index, 1),
            "heat_level": heat_level,
            "heat_desc": heat_desc,
            "new_listings_30d": new_listings_30d,
            "total_listings": total_listings,
            "auction_count": auction_count,
            "avg_unit_price": round(avg_unit_price, 2) if avg_unit_price else None,
            "components": {
                "new_listing_score": round(new_listing_score, 1),
                "auction_score": round(auction_score, 1),
                "price_score": round(price_score, 1)
            }
        }
    
    def update_all_community_stats(self):
        """更新所有小区统计信息"""
        communities = self.calculate_all_communities()
        
        for comm in communities:
            stats = {
                'community_name': comm['community_name'],
                'district': comm['district'],
                'total_listings': comm['listing_count'],
                'avg_unit_price': comm.get('avg_unit_price'),
                'turnover_rate': comm.get('turnover_rate')
            }
            self.db.update_community_stats(stats)
        
        return len(communities)
