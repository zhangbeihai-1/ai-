from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response, jsonify
import sqlite3
import os
import psutil
import datetime
import json
import time
import random

main_bp = Blueprint('main', __name__)

def get_db_connection():
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', 'data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@main_bp.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@main_bp.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        # In a real app, you'd use flash or a JSON response for the AJAX login
        return redirect(url_for('main.dashboard'))
    else:
        # Simple error handling for prototype
        return "登录失败，请检查用户名或密码", 401

from app.services.spider_service import SpiderService
from app.services.ai_service import AIService
from app.services.deep_crawl_service import DeepCrawlService

_spider_service = None
_ai_service = None
_deep_crawl_service = None

def get_spider_service():
    global _spider_service
    if _spider_service is None:
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', 'data.db')
        _spider_service = SpiderService(db_path)
    return _spider_service

def get_ai_service():
    global _ai_service
    if _ai_service is None:
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', 'data.db')
        _ai_service = AIService(db_path)
    return _ai_service

def get_deep_crawl_service():
    global _deep_crawl_service
    if _deep_crawl_service is None:
        db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', 'data.db')
        _deep_crawl_service = DeepCrawlService(db_path)
    return _deep_crawl_service

@main_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('main.index'))
    
    conn = get_db_connection()
    
    # 1. 动态获取核心统计指标
    total_data_count = conn.execute('SELECT COUNT(*) FROM collected_data').fetchone()[0]
    total_spiders_count = conn.execute('SELECT COUNT(*) FROM crawlers').fetchone()[0]
    
    ai_service = get_ai_service()
    ai_models = ai_service.get_all_models()
    active_ai_count = sum(1 for m in ai_models if m.get('is_active'))
    ai_status = "正常" if active_ai_count > 0 else "未接入"
    
    # 计算运行天数
    boot_time = psutil.boot_time()
    uptime_days = f"{int((time.time() - boot_time) / 86400)}天"
    
    stats = {
        'total_data': "{:,}".format(total_data_count),
        'total_spiders': str(total_spiders_count),
        'ai_engine_status': ai_status,
        'network_status': '良好',
        'system_uptime': uptime_days
    }
    
    # 2. 动态生成数据采集趋势 (最近7天)
    acquisition_data = {'days': [], 'values': []}
    for i in range(6, -1, -1):
        target_date = datetime.datetime.now() - datetime.timedelta(days=i)
        day_label = target_date.strftime('%m-%d')
        query_date = target_date.strftime('%Y-%m-%d')
        count = conn.execute("SELECT COUNT(*) FROM collected_data WHERE collect_time LIKE ?", (f"{query_date}%",)).fetchone()[0]
        acquisition_data['days'].append(day_label)
        acquisition_data['values'].append(count)
    
    # 3. 动态生成数据来源分布 (饼图)
    source_rows = conn.execute("SELECT source, COUNT(*) as count FROM collected_data GROUP BY source").fetchall()
    sentiment_data = []
    colors = ['#165DFF', '#722ED1', '#F5222D', '#52C41A', '#13C2C2', '#FAAD14']
    
    if not source_rows:
        sentiment_data = [
            {'name': '百度搜索', 'value': 40, 'itemStyle': {'color': '#165DFF'}},
            {'name': '百度新闻', 'value': 25, 'itemStyle': {'color': '#722ED1'}},
            {'name': '360搜索', 'value': 20, 'itemStyle': {'color': '#F5222D'}}
        ]
    else:
        for i, row in enumerate(source_rows):
            name = row['source']
            if name == 'baidu_search': name = '百度搜索'
            elif name == 'baidu_news': name = '百度新闻'
            elif name == '360_search': name = '360搜索'
            sentiment_data.append({
                'name': name,
                'value': row['count'],
                'itemStyle': {'color': colors[i % len(colors)]}
            })

    total_tokens = sum(m.get('used_tokens', 0) for m in ai_models)
    spider_service = get_spider_service()
    crawlers = spider_service.get_all_crawlers()
    collected_data, _ = spider_service.get_collected_data(page=1, per_page=10)
    conn.close()
    
    return render_template('dashboard.html', 
                          stats=stats, 
                          acquisition_data=acquisition_data,
                          sentiment_data=sentiment_data,
                          crawlers=crawlers,
                          collected_data=collected_data,
                          total_count=total_data_count,
                          ai_models=ai_models,
                          total_tokens=total_tokens)

@main_bp.route('/crawler/run/<int:crawler_id>', methods=['POST'])
def run_crawler(crawler_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    keyword = request.json.get('keyword', 'AI舆情')
    limit = request.json.get('limit', 10)
    
    spider_service = get_spider_service()
    try:
        count = spider_service.run_baidu_spider(crawler_id, keyword, limit=limit)
        return {"message": f"成功采集 {count} 条数据", "count": count}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/api/system_stats')
def get_system_stats():
    """获取真实系统资源监控数据"""
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    try:
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # 计算系统启动到现在的秒数
        boot_time = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_time)
        uptime_str = f"{uptime_seconds // 3600}小时 { (uptime_seconds % 3600) // 60 }分"
        
        return {
            "cpu": cpu_usage,
            "memory": memory.percent,
            "disk": disk.percent,
            "uptime": uptime_str,
            "net_io": psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv,
            "time": datetime.datetime.now().strftime("%H:%M:%S")
        }
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/crawler/stream')
def stream_crawler():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    crawler_id = request.args.get('id', type=int)
    keyword = request.args.get('keyword', 'AI舆情')
    limit = request.args.get('limit', 10, type=int)

    def generate():
        spider_service = get_spider_service()
        conn = get_db_connection()
        crawler = conn.execute('SELECT name, type FROM crawlers WHERE id = ?', (crawler_id,)).fetchone()
        conn.close()
        
        if not crawler:
            yield f"data: {json.dumps({'error': 'Crawler not found'})}\n\n"
            return

        from dist.baidusearch.search_cli import BaiduSpider, BaiduNewsSpider, SoSpider
        
        # 根据名称或类型选择爬虫类
        if '新闻' in crawler['name'] or crawler['type'] == 'baidu_news':
            spider = BaiduNewsSpider()
        elif '360' in crawler['name'] or crawler['type'] == '360_search':
            spider = SoSpider()
        else:
            spider = BaiduSpider()
        
        try:
            for item in spider.search(keyword, limit=limit):
                # Send each item as a JSON string in SSE format
                yield f"data: {json.dumps(item)}\n\n"
            
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@main_bp.route('/data/save', methods=['POST'])
def save_data():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    items = request.json.get('items', [])
    if not items:
        return {"error": "No items to save"}, 400
    
    conn = get_db_connection()
    new_added = 0
    updated = 0
    try:
        for item in items:
            # 检查 URL 是否已存在
            existing = conn.execute('SELECT id FROM collected_data WHERE url = ?', (item['url'],)).fetchone()
            if existing:
                conn.execute('''
                    UPDATE collected_data 
                    SET title = ?, description = ?, collect_time = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (item['title'], item['description'], existing['id']))
                updated += 1
            else:
                conn.execute('''
                    INSERT INTO collected_data (title, url, description, source)
                    VALUES (?, ?, ?, ?)
                ''', (item['title'], item['url'], item['description'], item['source']))
                new_added += 1
        
        # 仅针对新增条数更新系统统计量
        if new_added > 0:
            current_stats = conn.execute('SELECT metric_value FROM system_stats WHERE metric_name = ?', ('total_data',)).fetchone()
            if current_stats:
                try:
                    current_val = int(current_stats['metric_value'].replace(',', ''))
                    new_val = current_val + new_added
                    formatted_val = "{:,}".format(new_val)
                    conn.execute('UPDATE system_stats SET metric_value = ? WHERE metric_name = ?', (formatted_val, 'total_data'))
                except:
                    pass
            
        conn.commit()
        return {
            "message": f"保存完成！新增 {new_added} 条，更新 {updated} 条。",
            "added": new_added,
            "updated": updated
        }, 200
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        conn.close()

@main_bp.route('/crawler/add', methods=['POST'])
def add_new_crawler():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    data = request.json
    name = data.get('name')
    spider_type = data.get('type')  # 'script' or 'generic'
    script_path = data.get('script_path')
    config = data.get('config')
    description = data.get('description')
    
    if not name or not spider_type:
        return {"error": "Name and Type are required"}, 400
    
    spider_service = get_spider_service()
    try:
        spider_service.add_crawler(name, spider_type, script_path, config, description)
        return {"message": "爬虫添加成功"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/data/list')
def list_data():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    keyword = request.args.get('keyword')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    spider_service = get_spider_service()
    data, total = spider_service.get_collected_data(keyword=keyword, page=page, per_page=per_page)
    return {"data": data, "total": total, "page": page, "per_page": per_page}, 200

@main_bp.route('/data/delete/<int:data_id>', methods=['POST'])
def delete_collected_data(data_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    spider_service = get_spider_service()
    try:
        spider_service.delete_data(data_id)
        return {"message": "数据删除成功"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/data/batch_delete', methods=['POST'])
def batch_delete_data():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    ids = request.json.get('ids', [])
    if not ids:
        return {"error": "No IDs provided"}, 400
    
    spider_service = get_spider_service()
    try:
        spider_service.batch_delete_data(ids)
        return {"message": f"成功删除 {len(ids)} 条数据"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

# AI 模型相关路由
@main_bp.route('/model/add', methods=['POST'])
def add_model():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    data = request.json
    try:
        get_ai_service().add_model(
            data['name'], 
            data['api_url'], 
            data['api_key'], 
            data['model_name'], 
            data.get('system_prompt', '你是一个专业的政企信息分析助手。')
        )
        return {"message": "模型配置添加成功"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/model/update', methods=['POST'])
def update_model_config():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    data = request.json
    model_id = data.get('id')
    name = data.get('name')
    api_url = data.get('api_url')
    api_key = data.get('api_key')
    model_name = data.get('model_name')
    system_prompt = data.get('system_prompt')
    
    if not model_id or not name:
        return {"error": "Missing required fields"}, 400
        
    ai_service = get_ai_service()
    try:
        ai_service.update_model(model_id, name, api_url, api_key, model_name, system_prompt)
        return {"message": "模型配置已更新"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/model/delete/<int:model_id>', methods=['POST'])
def delete_model(model_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    try:
        get_ai_service().delete_model(model_id)
        return {"message": "模型配置已删除"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/model/test-chat', methods=['POST'])
def model_test_chat():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    data = request.json
    model_id = data.get('model_id')
    message = data.get('message')
    
    if not model_id or not message:
        return {"error": "Missing parameters"}, 400
    
    try:
        result = get_ai_service().chat_test(model_id, message)
        if "error" in result:
            return result, 500
        return result, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/model/chat-stream')
def model_chat_stream():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    model_id = request.args.get('model_id')
    message = request.args.get('message')
    
    if not model_id or not message:
        return {"error": "Missing parameters"}, 400
    
    ai_service = get_ai_service()
    return Response(
        ai_service.chat_stream(int(model_id), message),
        mimetype='text/event-stream'
    )

# 深度采集相关路由
@main_bp.route('/data/deep_crawl')
def deep_crawl_task():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    source_ids_str = request.args.get('ids', '')
    model_id = request.args.get('model_id')
    
    if not source_ids_str or not model_id:
        return {"error": "Missing parameters"}, 400
    
    source_ids = [int(sid) for sid in source_ids_str.split(',') if sid]
    deep_service = get_deep_crawl_service()
    
    return Response(
        deep_service.run_deep_crawl_task(source_ids, int(model_id)),
        mimetype='text/event-stream'
    )

@main_bp.route('/deep_data/list')
def list_deep_data():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    keyword = request.args.get('keyword')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    deep_service = get_deep_crawl_service()
    data, total = deep_service.get_deep_data(keyword=keyword, page=page, per_page=per_page)
    return {"data": data, "total": total, "page": page, "per_page": per_page}, 200

@main_bp.route('/deep_data/delete/<int:data_id>', methods=['POST'])
def delete_deep_data(data_id):
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    deep_service = get_deep_crawl_service()
    try:
        deep_service.delete_deep_data(data_id)
        return {"message": "深度采集数据已删除"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/deep_data/batch_delete', methods=['POST'])
def batch_delete_deep_data():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    ids = request.json.get('ids', [])
    if not ids:
        return {"error": "No IDs provided"}, 400
    
    deep_service = get_deep_crawl_service()
    try:
        deep_service.batch_delete_deep_data(ids)
        return {"message": f"成功删除 {len(ids)} 条深度数据"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/deep_data/update', methods=['POST'])
def update_deep_data():
    if 'user_id' not in session:
        return {"error": "Unauthorized"}, 401
    
    data = request.json
    try:
        get_deep_crawl_service().update_deep_data(
            data['id'],
            data['title'],
            data['content'],
            data['summary'],
            data['structured_data']
        )
        return {"message": "深度采集内容已更新"}, 200
    except Exception as e:
        return {"error": str(e)}, 500

@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))
@main_bp.route('/analysis/chat-stream', methods=['POST'])
def chat_analysis_stream():
    """AI 分析流式输出"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    model_id = data.get('model_id')
    message = data.get('message')
    conversation_id = data.get('conversation_id') # 新增：支持会话 ID

    if not model_id or not message:
        return jsonify({'error': 'Missing parameters'}), 400
    
    # 自动创建或保存消息
    conn = get_db_connection()
    if not conversation_id:
        # 如果没有会话 ID，自动创建一个
        title = message[:20] + "..." if len(message) > 20 else message
        cursor = conn.cursor()
        cursor.execute('INSERT INTO analysis_conversations (title, model_id) VALUES (?, ?)', (title, model_id))
        conversation_id = cursor.lastrowid
        conn.commit()
    
    # 保存用户消息
    conn.execute('INSERT INTO analysis_messages (conversation_id, role, content) VALUES (?, ?, ?)',
                (conversation_id, 'user', message))
    conn.commit()
    conn.close()

    ai_service = get_ai_service()
    
    def generate():
        full_response = ""
        # 传入 conversation_id 供 AI 服务保存回复
        for chunk in ai_service.chat_analysis_stream(model_id, message, conversation_id):
            if chunk.startswith("data: "):
                try:
                    # 尝试解析内容以便累加
                    content = chunk[6:].strip()
                    if content and not content.startswith('{'): # 排除图表 JSON 等
                        full_response += content
                except:
                    pass
            yield chunk
        
        # 对话结束后（在此处或 AI 服务内部）保存助手消息
        # 我们选择在 AIService 内部保存以获取完整且带标签的 raw_content
        pass

    return Response(generate(), mimetype='text/event-stream')

@main_bp.route('/analysis/conversations', methods=['GET'])
def get_conversations():
    """获取所有通话列表"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    conversations = conn.execute('''
        SELECT c.*, m.name as model_name 
        FROM analysis_conversations c
        JOIN ai_models m ON c.model_id = m.id
        ORDER BY c.create_time DESC
    ''').fetchall()
    
    result = []
    for row in conversations:
        result.append(dict(row))
    conn.close()
    return jsonify(result)

@main_bp.route('/analysis/new-chat', methods=['POST'])
def create_new_chat():
    """创建新会话"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    model_id = data.get('model_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO analysis_conversations (title, model_id) VALUES (?, ?)', ('新会话', model_id))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': new_id, 'title': '新会话'})

@main_bp.route('/analysis/conversation/<int:id>', methods=['GET'])
def get_conversation_history(id):
    """获取单次会话的历史消息"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    messages = conn.execute('''
        SELECT * FROM analysis_messages 
        WHERE conversation_id = ? 
        ORDER BY create_time ASC
    ''', (id,)).fetchall()
    
    result = []
    for row in messages:
        result.append(dict(row))
    conn.close()
    return jsonify(result)

@main_bp.route('/analysis/conversation/<int:id>', methods=['DELETE'])
def delete_conversation(id):
    """删除会话"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    conn.execute('DELETE FROM analysis_conversations WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})
