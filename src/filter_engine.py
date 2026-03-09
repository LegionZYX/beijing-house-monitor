"""
房源筛选引擎
"""
from typing import Dict, List, Any


class FilterEngine:
    """房源筛选引擎"""
    
    # 默认筛选条件（用户未指定时使用）
    DEFAULT_FILTERS = {
        'districts': ['朝阳', '海淀', '东城', '顺义'],
        'house_types': ['second_hand', 'auction'],
        'min_area': 120,
        'max_price': 500,
        'max_build_year': 2010,  # 楼龄不超过15年
        'require_elevator': True,
    }
    
    def __init__(self, filters: Dict = None):
        """
        Args:
            filters: 自定义筛选条件，None则使用默认条件
        """
        self.filters = filters or self.DEFAULT_FILTERS.copy()
    
    def match(self, house: Dict[str, Any]) -> bool:
        """
        判断房源是否符合筛选条件
        
        Args:
            house: 房源数据字典
            
        Returns:
            是否符合条件
        """
        # 区域筛选
        if self.filters.get('districts'):
            if house.get('district') not in self.filters['districts']:
                return False
        
        # 房源类型筛选
        if self.filters.get('house_types'):
            if house.get('house_type') not in self.filters['house_types']:
                return False
        
        # 面积筛选
        area = house.get('area_size')
        if area is not None:
            if self.filters.get('min_area') and area < self.filters['min_area']:
                return False
            if self.filters.get('max_area') and area > self.filters['max_area']:
                return False
        
        # 价格筛选（单位：万元）
        price = house.get('total_price')
        if price is not None:
            if self.filters.get('min_price') and price < self.filters['min_price']:
                return False
            if self.filters.get('max_price') and price > self.filters['max_price']:
                return False
        
        # 居室筛选
        rooms = house.get('rooms')
        if rooms is not None:
            if self.filters.get('min_rooms') and rooms < self.filters['min_rooms']:
                return False
            if self.filters.get('max_rooms') and rooms > self.filters['max_rooms']:
                return False
        
        # 电梯要求
        if self.filters.get('require_elevator'):
            if not house.get('has_elevator'):
                return False
        
        # 楼龄筛选
        build_year = house.get('build_year')
        if build_year is not None and self.filters.get('max_build_year'):
            if build_year < self.filters['max_build_year']:
                return False
        
        # 仅法拍房
        if self.filters.get('auction_only'):
            if house.get('house_type') != 'auction':
                return False
        
        # 小区名称筛选
        if self.filters.get('community_names'):
            if house.get('community_name') not in self.filters['community_names']:
                return False
        
        # 关键词筛选（标题、描述中包含指定关键词）
        if self.filters.get('keywords'):
            title = house.get('title', '')
            description = house.get('description', '')
            text = f"{title} {description}".lower()
            if not any(kw.lower() in text for kw in self.filters['keywords']):
                return False
        
        # 排除关键词
        if self.filters.get('exclude_keywords'):
            title = house.get('title', '')
            description = house.get('description', '')
            text = f"{title} {description}".lower()
            if any(kw.lower() in text for kw in self.filters['exclude_keywords']):
                return False
        
        return True
    
    def calculate_match_score(self, house: Dict[str, Any]) -> float:
        """
        计算匹配度评分（0-100）
        
        评分维度：
        - 价格合适度（40分）
        - 面积合适度（20分）
        - 楼龄（15分）
        - 电梯（10分）
        - 区域热门度（15分）
        
        Returns:
            匹配度得分
        """
        score = 0.0
        
        # 价格评分（40分）
        price = house.get('total_price')
        max_price = self.filters.get('max_price', 500)
        if price and max_price:
            if price <= max_price:
                # 价格越低得分越高
                price_ratio = price / max_price
                score += 40 * (1 - price_ratio * 0.5)  # 最高40分，最低20分
            else:
                # 超出预算扣分
                over_ratio = (price - max_price) / max_price
                score -= min(40, over_ratio * 40)
        
        # 面积评分（20分）
        area = house.get('area_size')
        min_area = self.filters.get('min_area', 120)
        if area and min_area:
            if area >= min_area:
                # 面积越大得分越高，但超过150平后增长放缓
                if area <= 150:
                    score += 20 * (area / 150)
                else:
                    score += 20
            else:
                # 面积不足扣分
                score -= min(20, (min_area - area) / min_area * 20)
        
        # 楼龄评分（15分）
        build_year = house.get('build_year')
        if build_year:
            current_year = 2026
            age = current_year - build_year
            if age <= 5:
                score += 15
            elif age <= 10:
                score += 12
            elif age <= 15:
                score += 8
            else:
                score += max(0, 15 - (age - 15) * 0.5)
        
        # 电梯评分（10分）
        if house.get('has_elevator'):
            score += 10
        
        # 区域评分（15分）- 根据区域热门程度
        district_scores = {
            '海淀': 15,
            '朝阳': 14,
            '东城': 13,
            '西城': 13,
            '丰台': 10,
            '石景山': 9,
            '通州': 8,
            '昌平': 8,
            '大兴': 8,
            '顺义': 7,
            '房山': 6,
            '门头沟': 5,
            '平谷': 4,
            '怀柔': 4,
            '密云': 3,
            '延庆': 3,
        }
        district = house.get('district')
        if district in district_scores:
            score += district_scores[district]
        
        return max(0, min(100, score))
    
    def filter_houses(self, houses: List[Dict]) -> List[Dict]:
        """
        批量筛选房源
        
        Args:
            houses: 房源列表
            
        Returns:
            符合条件的房源列表（按匹配度排序）
        """
        matched = []
        for house in houses:
            if self.match(house):
                house_copy = house.copy()
                house_copy['match_score'] = self.calculate_match_score(house)
                matched.append(house_copy)
        
        # 按匹配度降序排序
        matched.sort(key=lambda x: x['match_score'], reverse=True)
        return matched
    
    def to_dict(self) -> Dict:
        """导出筛选条件为字典"""
        return self.filters.copy()
    
    @classmethod
    def from_dict(cls, filters: Dict) -> 'FilterEngine':
        """从字典创建筛选引擎"""
        return cls(filters)
    
    def update_filters(self, new_filters: Dict):
        """更新筛选条件"""
        self.filters.update(new_filters)
    
    def reset_to_default(self):
        """重置为默认筛选条件"""
        self.filters = self.DEFAULT_FILTERS.copy()
