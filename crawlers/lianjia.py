"""
链家爬虫
"""
import re
import json
from typing import List, Dict, Any
from urllib.parse import urljoin, quote
from .base import BaseCrawler


class LianjiaCrawler(BaseCrawler):
    """链家二手房爬虫"""
    
    name = "链家"
    source = "lianjia"
    base_url = "https://bj.lianjia.com"
    
    # 区域代码映射
    DISTRICT_MAP = {
        '朝阳': 'chaoyang',
        '海淀': 'haidian',
        '东城': 'dongcheng',
        '西城': 'xicheng',
        '丰台': 'fengtai',
        '石景山': 'shijingshan',
        '通州': 'tongzhou',
        '昌平': 'changping',
        '大兴': 'daxing',
        '顺义': 'shunyi',
        '房山': 'fangshan',
        '门头沟': 'mentougou',
        '平谷': 'pinggu',
        '怀柔': 'huairou',
        '密云': 'miyun',
        '延庆': 'yanqing',
    }
    
    def crawl(self, districts: List[str] = None, max_pages: int = 3, **kwargs) -> List[Dict[str, Any]]:
        """
        爬取链家二手房数据
        
        Args:
            districts: 区域列表，如 ['朝阳', '海淀']
            max_pages: 每个区域最大爬取页数
            
        Returns:
            房源列表
        """
        houses = []
        
        if not districts:
            districts = list(self.DISTRICT_MAP.keys())
        
        for district in districts:
            if district not in self.DISTRICT_MAP:
                print(f"Unknown district: {district}")
                continue
            
            district_code = self.DISTRICT_MAP[district]
            print(f"Crawling Lianjia {district}...")
            
            try:
                district_houses = self._crawl_district(district, district_code, max_pages)
                houses.extend(district_houses)
                print(f"  Found {len(district_houses)} houses in {district}")
            except Exception as e:
                print(f"  Error crawling {district}: {e}")
        
        return houses
    
    def _crawl_district(self, district: str, district_code: str, max_pages: int) -> List[Dict]:
        """爬取单个区域"""
        houses = []
        
        for page in range(1, max_pages + 1):
            url = f"{self.base_url}/ershoufang/{district_code}/pg{page}/"
            
            try:
                response = self._get(url)
                soup = self._parse_html(response.text)
                
                # 查找房源列表
                house_list = soup.find('ul', class_='sellListContent')
                if not house_list:
                    print(f"  No house list found on page {page}")
                    break
                
                items = house_list.find_all('li', class_='clear')
                if not items:
                    print(f"  No more items on page {page}")
                    break
                
                for item in items:
                    try:
                        house = self._parse_item(item, district)
                        if house:
                            houses.append(self.normalize_house(house))
                    except Exception as e:
                        print(f"  Error parsing item: {e}")
                        continue
                
            except Exception as e:
                print(f"  Error on page {page}: {e}")
                break
        
        return houses
    
    def _parse_item(self, item, district: str) -> Dict:
        """解析单个房源元素"""
        house = {
            'source': self.source,
            'house_type': 'second_hand',
            'district': district,
        }
        
        # 标题和链接
        title_elem = item.find('a', class_='title')
        if title_elem:
            house['title'] = title_elem.text.strip()
            house['source_url'] = title_elem.get('href', '')
            # 从URL中提取房源ID
            match = re.search(r'/(\d+)\.html', house['source_url'])
            if match:
                house['source_id'] = match.group(1)
        
        # 小区名称
        community_elem = item.find('a', attrs={'data-el': 'region'})
        if community_elem:
            house['community_name'] = community_elem.text.strip()
        
        # 地址/商圈
        address_elem = item.find('div', class_='houseInfo')
        if address_elem:
            address_text = address_elem.get_text(strip=True)
            house['address'] = address_text
            
            # 解析户型、面积等信息
            # 格式通常是：2室1厅 | 89.5平米 | 南 | 精装 | 有电梯
            parts = address_text.split('|')
            if len(parts) >= 2:
                # 户型
                layout = parts[0].strip()
                rooms_match = re.search(r'(\d+)室', layout)
                halls_match = re.search(r'(\d+)厅', layout)
                if rooms_match:
                    house['rooms'] = int(rooms_match.group(1))
                if halls_match:
                    house['halls'] = int(halls_match.group(1))
                
                # 面积
                area_match = re.search(r'([\d.]+)平米', parts[1])
                if area_match:
                    house['area_size'] = float(area_match.group(1))
        
        # 价格信息
        price_elem = item.find('div', class_='totalPrice')
        if price_elem:
            price_text = price_elem.get_text(strip=True)
            price_match = re.search(r'([\d.]+)', price_text)
            if price_match:
                house['total_price'] = float(price_match.group(1))
        
        unit_price_elem = item.find('div', class_='unitPrice')
        if unit_price_elem:
            unit_price_text = unit_price_elem.get_text(strip=True)
            unit_price_match = re.search(r'([\d,]+)', unit_price_text)
            if unit_price_match:
                house['unit_price'] = float(unit_price_match.group(1).replace(',', ''))
        
        # 楼层、年份、电梯等信息
        flood_elem = item.find('div', class_='flood')
        if flood_elem:
            flood_text = flood_elem.get_text(strip=True)
            
            # 楼层
            floor_match = re.search(r'(\d+)/(\d+)层', flood_text)
            if floor_match:
                house['floor'] = int(floor_match.group(1))
                house['total_floors'] = int(floor_match.group(2))
            
            # 建造年份
            year_match = re.search(r'(\d{4})年', flood_text)
            if year_match:
                house['build_year'] = int(year_match.group(1))
        
        # 标签
        tag_elems = item.find_all('span', class_='tag')
        house['tags'] = [tag.text.strip() for tag in tag_elems]
        
        # 检查是否有电梯标签
        house['has_elevator'] = any('电梯' in tag for tag in house['tags'])
        
        return house
    
    def parse_house(self, raw_data: Dict) -> Dict[str, Any]:
        """解析房源数据"""
        return self.normalize_house(raw_data)
