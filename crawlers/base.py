"""
爬虫基类
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import time
import random
import requests
from bs4 import BeautifulSoup


class BaseCrawler(ABC):
    """爬虫基类"""
    
    name: str = ""  # 爬虫名称
    source: str = ""  # 来源标识
    base_url: str = ""  # 基础URL
    
    # 请求配置
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    # 反爬设置
    min_delay: float = 2.0  # 最小请求间隔（秒）
    max_delay: float = 5.0  # 最大请求间隔（秒）
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.last_request_time = 0
    
    def _random_delay(self):
        """随机延迟，避免请求过快"""
        elapsed = time.time() - self.last_request_time
        delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request_time = time.time()
    
    def _get(self, url: str, **kwargs) -> requests.Response:
        """
        发送 GET 请求
        
        Args:
            url: 请求URL
            **kwargs: 其他 requests 参数
            
        Returns:
            Response 对象
        """
        self._random_delay()
        try:
            response = self.session.get(url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"Request failed: {url}, error: {e}")
            raise
    
    def _post(self, url: str, **kwargs) -> requests.Response:
        """发送 POST 请求"""
        self._random_delay()
        try:
            response = self.session.post(url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"Request failed: {url}, error: {e}")
            raise
    
    def _parse_html(self, html: str) -> BeautifulSoup:
        """解析 HTML"""
        return BeautifulSoup(html, 'lxml')
    
    @abstractmethod
    def crawl(self, **kwargs) -> List[Dict[str, Any]]:
        """
        执行爬取
        
        Args:
            **kwargs: 爬取参数（如区域、页码等）
            
        Returns:
            房源列表
        """
        pass
    
    @abstractmethod
    def parse_house(self, raw_data: Dict) -> Dict[str, Any]:
        """
        解析单条房源数据
        
        Args:
            raw_data: 原始数据
            
        Returns:
            标准化的房源字典
        """
        pass
    
    def normalize_house(self, house: Dict) -> Dict[str, Any]:
        """
        标准化房源数据
        
        确保所有房源都有统一的字段格式
        """
        normalized = {
            'source': self.source,
            'source_id': str(house.get('source_id', '')),
            'house_type': house.get('house_type', 'second_hand'),
            'title': house.get('title', ''),
            'district': house.get('district', ''),
            'area_name': house.get('area_name', ''),
            'community_name': house.get('community_name', ''),
            'address': house.get('address', ''),
            'total_price': self._parse_price(house.get('total_price')),
            'unit_price': self._parse_price(house.get('unit_price')),
            'area_size': self._parse_area(house.get('area_size')),
            'rooms': house.get('rooms'),
            'halls': house.get('halls'),
            'floor': house.get('floor'),
            'total_floors': house.get('total_floors'),
            'has_elevator': house.get('has_elevator', False),
            'build_year': house.get('build_year'),
            'tags': house.get('tags', []),
            'description': house.get('description', ''),
            'source_url': house.get('source_url', ''),
            'images': house.get('images', []),
        }
        
        # 法拍房特有字段
        if normalized['house_type'] == 'auction':
            normalized.update({
                'auction_status': house.get('auction_status'),
                'auction_start_time': house.get('auction_start_time'),
                'auction_end_time': house.get('auction_end_time'),
                'deposit': self._parse_price(house.get('deposit')),
                'starting_price': self._parse_price(house.get('starting_price')),
                'market_price': self._parse_price(house.get('market_price')),
            })
        
        return normalized
    
    def _parse_price(self, price) -> float:
        """
        解析价格
        
        支持格式：
        - 500（万元）
        - "500万"
        - "500万元"
        - "5,000,000"
        """
        if price is None:
            return None
        
        if isinstance(price, (int, float)):
            return float(price)
        
        if isinstance(price, str):
            # 移除单位和非数字字符
            price = price.replace(',', '').replace('万', '').replace('元', '').strip()
            try:
                return float(price)
            except ValueError:
                return None
        
        return None
    
    def _parse_area(self, area) -> float:
        """
        解析面积
        
        支持格式：
        - 120（平米）
        - "120㎡"
        - "120平米"
        """
        if area is None:
            return None
        
        if isinstance(area, (int, float)):
            return float(area)
        
        if isinstance(area, str):
            area = area.replace('㎡', '').replace('平米', '').replace('m²', '').strip()
            try:
                return float(area)
            except ValueError:
                return None
        
        return None
