"""
京东法拍房爬虫
"""
import re
import json
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseCrawler


class JDAuctionCrawler(BaseCrawler):
    """京东法拍房爬虫"""
    
    name = "京东法拍"
    source = "jd_auction"
    base_url = "https://auction.jd.com"
    
    # 北京区域代码（京东的编码）
    BEIJING_CODE = "1_0_0"  # 需要根据实际API调整
    
    def crawl(self, max_pages: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """
        爬取京东法拍房数据
        
        Args:
            max_pages: 最大爬取页数
            
        Returns:
            房源列表
        """
        houses = []
        print("Crawling JD Auction...")
        
        for page in range(1, max_pages + 1):
            try:
                page_houses = self._crawl_page(page)
                if not page_houses:
                    break
                houses.extend(page_houses)
                print(f"  Page {page}: {len(page_houses)} items")
            except Exception as e:
                print(f"  Error on page {page}: {e}")
                break
        
        print(f"Total JD auction houses: {len(houses)}")
        return houses
    
    def _crawl_page(self, page: int) -> List[Dict]:
        """爬取单页数据"""
        # 京东法拍房API（需要根据实际情况调整）
        url = f"{self.base_url}/sifa_list.html"
        params = {
            'page': page,
            'province': '北京市',
        }
        
        response = self._get(url, params=params)
        soup = self._parse_html(response.text)
        
        houses = []
        
        # 查找拍卖列表
        items = soup.find_all('li', class_='ui-list-item') or soup.find_all('div', class_='item')
        
        for item in items:
            try:
                house = self._parse_item(item)
                if house:
                    houses.append(self.normalize_house(house))
            except Exception as e:
                print(f"  Error parsing item: {e}")
                continue
        
        return houses
    
    def _parse_item(self, item) -> Dict:
        """解析单个拍卖项"""
        house = {
            'source': self.source,
            'house_type': 'auction',
        }
        
        # 标题和链接
        title_elem = item.find('a', class_='title') or item.find('h3')
        if title_elem:
            link_elem = title_elem.find_parent('a') or title_elem
            house['title'] = title_elem.get_text(strip=True)
            house['source_url'] = link_elem.get('href', '')
            if house['source_url'].startswith('/'):
                house['source_url'] = f"{self.base_url}{house['source_url']}"
            
            # 提取ID
            match = re.search(r'(\d+)\.html', house['source_url'])
            if match:
                house['source_id'] = f"jd_{match.group(1)}"
        
        # 图片
        img_elem = item.find('img')
        if img_elem:
            house['images'] = [img_elem.get('src', '')]
        
        # 价格信息
        price_elem = item.find('span', class_='price') or item.find('div', class_='p-price')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            
            # 起拍价
            starting_match = re.search(r'起拍价[:：]?\s*([\d.]+)', price_text)
            if starting_match:
                house['starting_price'] = float(starting_match.group(1))
            
            # 评估价/市场价
            market_match = re.search(r'评估价[:：]?\s*([\d.]+)', price_text)
            if market_match:
                house['market_price'] = float(market_match.group(1))
            
            # 如果没有明确标注，尝试直接提取数字
            if 'starting_price' not in house:
                price_nums = re.findall(r'([\d.]+)', price_text.replace(',', ''))
                if price_nums:
                    house['starting_price'] = float(price_nums[0])
        
        # 保证金
        deposit_elem = item.find('span', text=re.compile('保证金')) or item.find('div', text=re.compile('保证金'))
        if deposit_elem:
            deposit_text = deposit_elem.get_text(strip=True)
            deposit_match = re.search(r'([\d.]+)', deposit_text.replace(',', ''))
            if deposit_match:
                house['deposit'] = float(deposit_match.group(1))
        
        # 位置信息
        location_elem = item.find('span', class_='location') or item.find('div', class_='p-area')
        if location_elem:
            location_text = location_elem.get_text(strip=True)
            house['address'] = location_text
            
            # 解析区域
            for district in ['朝阳', '海淀', '东城', '西城', '丰台', '石景山', '通州', 
                           '昌平', '大兴', '顺义', '房山', '门头沟']:
                if district in location_text:
                    house['district'] = district
                    break
        
        # 面积信息
        area_elem = item.find(text=re.compile(r'\d+\.?\d*\s*㎡'))
        if area_elem:
            area_match = re.search(r'([\d.]+)\s*㎡', area_elem)
            if area_match:
                house['area_size'] = float(area_match.group(1))
        
        # 拍卖时间
        time_elem = item.find('span', class_='time') or item.find('div', class_='p-time')
        if time_elem:
            time_text = time_elem.get_text(strip=True)
            
            # 解析开拍时间
            start_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', time_text)
            if start_match:
                house['auction_start_time'] = start_match.group(1)
            
            # 状态判断
            if '即将开始' in time_text or '预告' in time_text:
                house['auction_status'] = 'upcoming'
            elif '进行中' in time_text or '竞价中' in time_text:
                house['auction_status'] = 'ongoing'
            elif '已结束' in time_text or '成交' in time_text:
                house['auction_status'] = 'completed'
        
        # 设置总价为起拍价（用于筛选）
        if 'starting_price' in house:
            house['total_price'] = house['starting_price']
        
        # 默认有电梯（法拍房通常是住宅楼）
        house['has_elevator'] = True
        
        return house
    
    def parse_house(self, raw_data: Dict) -> Dict[str, Any]:
        """解析房源数据"""
        return self.normalize_house(raw_data)
