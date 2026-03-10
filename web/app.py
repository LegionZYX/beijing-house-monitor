"""
Web 仪表盘 - Flask 应用
"""
import os
import sys
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, abort, Response

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import Database
from src.filter_engine import FilterEngine

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# 初始化数据库
# Railway 使用环境变量 DATABASE_PATH，本地使用项目目录
db_path = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'houses.db'))
db = Database(db_path)

# 基础认证
def check_auth():
    """检查认证"""
    auth = request.authorization
    if not auth:
        return False
    username = os.environ.get('WEB_USERNAME', 'admin')
    password = os.environ.get('WEB_PASSWORD', 'admin')
    return auth.username == username and auth.password == password

@app.before_request
def require_auth():
    """要求认证（除了健康检查）"""
    if request.endpoint in ['health', 'static']:
        return None
    if not check_auth():
        # 返回 401 并触发浏览器认证弹窗
        return Response(
            'Authentication required',
            401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'}
        )

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})

@app.route('/')
def index():
    """首页仪表盘"""
    stats = db.get_stats()
    
    # 获取今日新增
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # 最近24小时新增
        cursor.execute("""
            SELECT COUNT(*) FROM houses 
            WHERE first_seen_at >= datetime('now', '-1 day')
            AND is_deleted = FALSE
        """)
        recent_new = cursor.fetchone()[0]
        
        # 即将开始的法拍房
        cursor.execute("""
            SELECT COUNT(*) FROM houses 
            WHERE house_type = 'auction' 
            AND auction_status = 'upcoming'
            AND is_deleted = FALSE
        """)
        upcoming_auctions = cursor.fetchone()[0]
        
        # 最近降价房源
        cursor.execute("""
            SELECT h.*, MIN(ph.price) as min_price
            FROM houses h
            JOIN price_history ph ON h.id = ph.house_id
            WHERE h.is_deleted = FALSE
            AND ph.recorded_at >= datetime('now', '-7 days')
            GROUP BY h.id
            HAVING h.total_price < min_price
            LIMIT 5
        """)
        price_drops = [dict(row) for row in cursor.fetchall()]
    
    return render_template('index.html',
                         stats=stats,
                         recent_new=recent_new,
                         upcoming_auctions=upcoming_auctions,
                         price_drops=price_drops)

@app.route('/houses')
def houses():
    """房源列表页"""
    # 获取筛选参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 构建筛选条件
    filters = {}
    
    districts = request.args.getlist('district')
    if districts:
        filters['districts'] = districts
    
    house_types = request.args.getlist('type')
    if house_types:
        filters['house_types'] = house_types
    
    min_price = request.args.get('min_price', type=float)
    if min_price:
        filters['min_price'] = min_price
    
    max_price = request.args.get('max_price', type=float)
    if max_price:
        filters['max_price'] = max_price
    
    min_area = request.args.get('min_area', type=float)
    if min_area:
        filters['min_area'] = min_area
    
    max_area = request.args.get('max_area', type=float)
    if max_area:
        filters['max_area'] = max_area
    
    if request.args.get('elevator'):
        filters['require_elevator'] = True
    
    # 获取房源
    offset = (page - 1) * per_page
    house_list = db.get_houses(filters=filters if filters else None, 
                               limit=per_page, offset=offset)
    
    # 获取总数
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM houses WHERE is_deleted = FALSE")
        total = cursor.fetchone()[0]
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('houses.html',
                         houses=house_list,
                         page=page,
                         per_page=per_page,
                         total=total,
                         total_pages=total_pages,
                         filters=request.args)

@app.route('/houses/<int:house_id>')
def house_detail(house_id):
    """房源详情页"""
    house = db.get_house_by_id(house_id)
    if not house:
        abort(404)
    
    # 获取价格历史
    price_history = db.get_price_history(house_id, days=90)
    
    # 获取同小区房源
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM houses 
            WHERE community_name = ? 
            AND district = ?
            AND id != ?
            AND is_deleted = FALSE
            LIMIT 5
        """, (house.get('community_name'), house.get('district'), house_id))
        similar_houses = [dict(row) for row in cursor.fetchall()]
    
    return render_template('house_detail.html',
                         house=house,
                         price_history=price_history,
                         similar_houses=similar_houses)

@app.route('/auctions')
def auctions():
    """法拍房专页"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # 即将开始的法拍房
        cursor.execute("""
            SELECT * FROM houses 
            WHERE house_type = 'auction' 
            AND auction_status = 'upcoming'
            AND is_deleted = FALSE
            ORDER BY auction_start_time ASC
        """)
        upcoming = [dict(row) for row in cursor.fetchall()]
        
        # 进行中的法拍房
        cursor.execute("""
            SELECT * FROM houses 
            WHERE house_type = 'auction' 
            AND auction_status = 'ongoing'
            AND is_deleted = FALSE
        """)
        ongoing = [dict(row) for row in cursor.fetchall()]
    
    return render_template('auctions.html',
                         upcoming=upcoming,
                         ongoing=ongoing)

@app.route('/trends')
def trends():
    """价格趋势页"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # 各区域平均价格
        cursor.execute("""
            SELECT district, 
                   AVG(total_price) as avg_price,
                   AVG(unit_price) as avg_unit_price,
                   COUNT(*) as count
            FROM houses 
            WHERE is_deleted = FALSE
            AND total_price IS NOT NULL
            GROUP BY district
            ORDER BY avg_unit_price DESC
        """)
        district_stats = [dict(row) for row in cursor.fetchall()]
        
        # 热门小区
        cursor.execute("""
            SELECT community_name, district,
                   AVG(total_price) as avg_price,
                   AVG(unit_price) as avg_unit_price,
                   COUNT(*) as listing_count
            FROM houses 
            WHERE is_deleted = FALSE
            AND total_price IS NOT NULL
            AND community_name IS NOT NULL
            GROUP BY community_name, district
            HAVING listing_count >= 3
            ORDER BY listing_count DESC
            LIMIT 20
        """)
        top_communities = [dict(row) for row in cursor.fetchall()]
    
    return render_template('trends.html',
                         district_stats=district_stats,
                         top_communities=top_communities)

@app.route('/settings')
def settings():
    """设置页"""
    return render_template('settings.html')

# API 路由
@app.route('/api/houses')
def api_houses():
    """API: 获取房源列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    filters = {}
    if request.args.get('district'):
        filters['districts'] = request.args.getlist('district')
    
    offset = (page - 1) * per_page
    houses = db.get_houses(filters=filters, limit=per_page, offset=offset)
    
    return jsonify({
        'houses': houses,
        'page': page,
        'per_page': per_page
    })

@app.route('/api/houses/<int:house_id>')
def api_house_detail(house_id):
    """API: 获取房源详情"""
    house = db.get_house_by_id(house_id)
    if not house:
        return jsonify({'error': 'Not found'}), 404
    
    price_history = db.get_price_history(house_id)
    
    return jsonify({
        'house': house,
        'price_history': price_history
    })

@app.route('/api/stats')
def api_stats():
    """API: 获取统计数据"""
    stats = db.get_stats()
    return jsonify(stats)

if __name__ == '__main__':
    # Railway 使用 PORT 环境变量
    port = int(os.environ.get('PORT', 8080))
    # 生产环境关闭 debug
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
