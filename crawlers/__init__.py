"""
爬虫模块
"""
from .base import BaseCrawler
from .lianjia import LianjiaCrawler
from .beike import BeikeCrawler
from .jd_auction import JDAuctionCrawler

__all__ = [
    'BaseCrawler',
    'LianjiaCrawler',
    'BeikeCrawler',
    'JDAuctionCrawler',
]

# 爬虫注册表
CRAWLERS = {
    'lianjia': LianjiaCrawler,
    'beike': BeikeCrawler,
    'jd_auction': JDAuctionCrawler,
}

def get_crawler(name: str) -> type:
    """获取爬虫类"""
    return CRAWLERS.get(name)

def list_crawlers() -> list:
    """列出所有可用爬虫"""
    return list(CRAWLERS.keys())
