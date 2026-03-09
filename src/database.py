"""
数据库操作模块
"""
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import contextmanager
import os


class Database:
    """SQLite 数据库操作类"""
    
    def __init__(self, db_path: str = None):
        # Railway 使用持久化卷 /app/data
        # 本地开发使用项目目录下的 data
        if db_path is None:
            db_path = os.environ.get('DATABASE_PATH', 'data/houses.db')
        
        self.db_path = db_path
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_tables()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接上下文"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_tables(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 房源表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS houses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    house_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    district TEXT NOT NULL,
                    area_name TEXT,
                    community_name TEXT,
                    address TEXT,
                    total_price REAL,
                    unit_price REAL,
                    area_size REAL,
                    rooms INTEGER,
                    halls INTEGER,
                    floor INTEGER,
                    total_floors INTEGER,
                    has_elevator BOOLEAN,
                    build_year INTEGER,
                    auction_status TEXT,
                    auction_start_time TIMESTAMP,
                    auction_end_time TIMESTAMP,
                    deposit REAL,
                    starting_price REAL,
                    market_price REAL,
                    tags TEXT,
                    description TEXT,
                    source_url TEXT,
                    images TEXT,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN DEFAULT FALSE
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_houses_source ON houses(source, source_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_houses_district ON houses(district)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_houses_price ON houses(total_price)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_houses_area ON houses(area_size)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_houses_type ON houses(house_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_houses_community ON houses(community_name)")
            
            # 价格历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    house_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    price_type TEXT NOT NULL,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (house_id) REFERENCES houses(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_house ON price_history(house_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_time ON price_history(recorded_at)")
            
            # 小区统计表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS community_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    community_name TEXT NOT NULL,
                    district TEXT NOT NULL,
                    total_listings INTEGER DEFAULT 0,
                    total_deals_90d INTEGER DEFAULT 0,
                    avg_unit_price REAL,
                    price_change_30d REAL,
                    price_change_90d REAL,
                    turnover_rate REAL,
                    price_distribution TEXT,
                    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(community_name, district)
                )
            """)
            
            # 用户订阅表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    filters TEXT NOT NULL,
                    notify_on_new BOOLEAN DEFAULT TRUE,
                    notify_on_price_drop BOOLEAN DEFAULT TRUE,
                    notify_channels TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 抓取日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crawl_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    houses_found INTEGER DEFAULT 0,
                    houses_new INTEGER DEFAULT 0,
                    houses_updated INTEGER DEFAULT 0,
                    houses_removed INTEGER DEFAULT 0,
                    error_message TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def save_house(self, house_data: Dict[str, Any]) -> int:
        """
        保存或更新房源
        
        Returns:
            房源ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查是否已存在
            cursor.execute(
                "SELECT id, total_price FROM houses WHERE source = ? AND source_id = ?",
                (house_data['source'], house_data['source_id'])
            )
            existing = cursor.fetchone()
            
            now = datetime.now().isoformat()
            
            # 处理列表/字典字段
            tags = json.dumps(house_data.get('tags', []), ensure_ascii=False) if isinstance(house_data.get('tags'), list) else house_data.get('tags')
            images = json.dumps(house_data.get('images', []), ensure_ascii=False) if isinstance(house_data.get('images'), list) else house_data.get('images')
            
            if existing:
                # 更新现有房源
                house_id = existing['id']
                old_price = existing['total_price']
                new_price = house_data.get('total_price')
                
                cursor.execute("""
                    UPDATE houses SET
                        title = ?, district = ?, area_name = ?, community_name = ?,
                        address = ?, total_price = ?, unit_price = ?, area_size = ?,
                        rooms = ?, halls = ?, floor = ?, total_floors = ?,
                        has_elevator = ?, build_year = ?, auction_status = ?,
                        auction_start_time = ?, auction_end_time = ?, deposit = ?,
                        starting_price = ?, market_price = ?, tags = ?, description = ?,
                        source_url = ?, images = ?, last_seen_at = ?, last_updated_at = ?,
                        is_deleted = FALSE
                    WHERE id = ?
                """, (
                    house_data.get('title'), house_data.get('district'),
                    house_data.get('area_name'), house_data.get('community_name'),
                    house_data.get('address'), new_price, house_data.get('unit_price'),
                    house_data.get('area_size'), house_data.get('rooms'),
                    house_data.get('halls'), house_data.get('floor'),
                    house_data.get('total_floors'), house_data.get('has_elevator'),
                    house_data.get('build_year'), house_data.get('auction_status'),
                    house_data.get('auction_start_time'), house_data.get('auction_end_time'),
                    house_data.get('deposit'), house_data.get('starting_price'),
                    house_data.get('market_price'), tags, house_data.get('description'),
                    house_data.get('source_url'), images, now, now, house_id
                ))
                
                # 如果价格变动，记录价格历史
                if old_price != new_price and new_price is not None:
                    self._record_price_change(conn, house_id, new_price, 'listing')
                    
                return house_id
            else:
                # 插入新房源
                cursor.execute("""
                    INSERT INTO houses (
                        source, source_id, house_type, title, district, area_name,
                        community_name, address, total_price, unit_price, area_size,
                        rooms, halls, floor, total_floors, has_elevator, build_year,
                        auction_status, auction_start_time, auction_end_time, deposit,
                        starting_price, market_price, tags, description, source_url, images
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    house_data.get('source'), house_data.get('source_id'),
                    house_data.get('house_type'), house_data.get('title'),
                    house_data.get('district'), house_data.get('area_name'),
                    house_data.get('community_name'), house_data.get('address'),
                    house_data.get('total_price'), house_data.get('unit_price'),
                    house_data.get('area_size'), house_data.get('rooms'),
                    house_data.get('halls'), house_data.get('floor'),
                    house_data.get('total_floors'), house_data.get('has_elevator'),
                    house_data.get('build_year'), house_data.get('auction_status'),
                    house_data.get('auction_start_time'), house_data.get('auction_end_time'),
                    house_data.get('deposit'), house_data.get('starting_price'),
                    house_data.get('market_price'), tags, house_data.get('description'),
                    house_data.get('source_url'), images
                ))
                
                house_id = cursor.lastrowid
                
                # 记录初始价格
                if house_data.get('total_price'):
                    self._record_price_change(conn, house_id, house_data['total_price'], 'listing')
                
                return house_id
    
    def _record_price_change(self, conn, house_id: int, price: float, price_type: str):
        """记录价格变动"""
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO price_history (house_id, price, price_type) VALUES (?, ?, ?)",
            (house_id, price, price_type)
        )
    
    def get_house_by_id(self, house_id: int) -> Optional[Dict]:
        """根据ID获取房源"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM houses WHERE id = ?", (house_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_houses(self, filters: Dict = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        获取房源列表
        
        Args:
            filters: 筛选条件
            limit: 返回数量限制
            offset: 偏移量
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM houses WHERE is_deleted = FALSE"
            params = []
            
            if filters:
                if filters.get('districts'):
                    placeholders = ','.join('?' * len(filters['districts']))
                    query += f" AND district IN ({placeholders})"
                    params.extend(filters['districts'])
                
                if filters.get('house_types'):
                    placeholders = ','.join('?' * len(filters['house_types']))
                    query += f" AND house_type IN ({placeholders})"
                    params.extend(filters['house_types'])
                
                if filters.get('min_price') is not None:
                    query += " AND total_price >= ?"
                    params.append(filters['min_price'])
                
                if filters.get('max_price') is not None:
                    query += " AND total_price <= ?"
                    params.append(filters['max_price'])
                
                if filters.get('min_area') is not None:
                    query += " AND area_size >= ?"
                    params.append(filters['min_area'])
                
                if filters.get('max_area') is not None:
                    query += " AND area_size <= ?"
                    params.append(filters['max_area'])
                
                if filters.get('require_elevator'):
                    query += " AND has_elevator = TRUE"
                
                if filters.get('max_build_year'):
                    query += " AND build_year >= ?"
                    params.append(filters['max_build_year'])
            
            query += " ORDER BY last_seen_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_price_history(self, house_id: int, days: int = 90) -> List[Dict]:
        """获取房源价格历史"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM price_history 
                WHERE house_id = ? 
                AND recorded_at >= datetime('now', '-{} days')
                ORDER BY recorded_at ASC
            """.format(days), (house_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_community_stats(self, community_name: str, district: str) -> Optional[Dict]:
        """获取小区统计"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM community_stats WHERE community_name = ? AND district = ?",
                (community_name, district)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_community_stats(self, stats: Dict):
        """更新小区统计"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO community_stats (
                    community_name, district, total_listings, total_deals_90d,
                    avg_unit_price, price_change_30d, price_change_90d,
                    turnover_rate, price_distribution, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stats['community_name'], stats['district'],
                stats.get('total_listings', 0), stats.get('total_deals_90d', 0),
                stats.get('avg_unit_price'), stats.get('price_change_30d'),
                stats.get('price_change_90d'), stats.get('turnover_rate'),
                json.dumps(stats.get('price_distribution', {})),
                datetime.now().isoformat()
            ))
    
    def log_crawl(self, source: str, status: str, houses_found: int = 0,
                  houses_new: int = 0, houses_updated: int = 0,
                  houses_removed: int = 0, error_message: str = None,
                  started_at: str = None):
        """记录抓取日志"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO crawl_logs (
                    source, status, houses_found, houses_new, houses_updated,
                    houses_removed, error_message, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source, status, houses_found, houses_new, houses_updated,
                houses_removed, error_message, started_at, datetime.now().isoformat()
            ))
    
    def get_stats(self) -> Dict:
        """获取统计数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 总房源数
            cursor.execute("SELECT COUNT(*) FROM houses WHERE is_deleted = FALSE")
            total_houses = cursor.fetchone()[0]
            
            # 今日新增
            cursor.execute("""
                SELECT COUNT(*) FROM houses 
                WHERE date(first_seen_at) = date('now')
            """)
            today_new = cursor.fetchone()[0]
            
            # 法拍房数量
            cursor.execute("SELECT COUNT(*) FROM houses WHERE house_type = 'auction'")
            auction_count = cursor.fetchone()[0]
            
            # 各区域分布
            cursor.execute("""
                SELECT district, COUNT(*) as count 
                FROM houses 
                WHERE is_deleted = FALSE
                GROUP BY district
            """)
            district_dist = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                'total_houses': total_houses,
                'today_new': today_new,
                'auction_count': auction_count,
                'district_distribution': district_dist
            }
