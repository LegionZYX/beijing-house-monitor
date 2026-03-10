"""
Railway 主启动脚本 - Web 服务
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_web():
    """运行 Web 服务"""
    print("[Railway] Starting web server...")
    from web.app import app
    port = int(os.environ.get('PORT', 8080))
    print(f"[Railway] Binding to port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

if __name__ == '__main__':
    print("=" * 50)
    print("Beijing House Monitor - Railway Deployment")
    print("=" * 50)
    run_web()
