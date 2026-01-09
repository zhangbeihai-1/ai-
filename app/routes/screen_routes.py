from flask import Blueprint, render_template, jsonify
import sqlite3
import os
from datetime import datetime, timedelta

screen_bp = Blueprint('screen', __name__)

def get_db_connection():
    db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', 'data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

@screen_bp.route('/screen')
def data_screen():
    """数智大屏页面"""
    return render_template('data_screen.html')

@screen_bp.route('/api/screen/overview')
def screen_overview():
    """获取大屏总览数据"""
    conn = get_db_connection()
    
    # 今日采集量
    today_count = conn.execute('''
        SELECT COUNT(*) as count FROM collected_data 
        WHERE DATE(collect_time) = DATE('now')
    ''').fetchone()['count']
    
    # 本周采集量
    week_count = conn.execute('''
        SELECT COUNT(*) as count FROM collected_data 
        WHERE DATE(collect_time) >= DATE('now', 'weekday 0', '-7 days')
    ''').fetchone()['count']
    
    # 本月采集量
    month_count = conn.execute('''
        SELECT COUNT(*) as count FROM collected_data 
        WHERE DATE(collect_time) >= DATE('now', 'start of month')
    ''').fetchone()['count']
    
    # 总采集量
    total_count = conn.execute('SELECT COUNT(*) as count FROM collected_data').fetchone()['count']
    
    # 深度采集量
    deep_count = conn.execute('''
        SELECT COUNT(*) as count FROM collected_data WHERE deep_status = 2
    ''').fetchone()['count']
    
    # 来源分布
    source_stats = conn.execute('''
        SELECT 
            source,
            COUNT(*) as count
        FROM collected_data
        GROUP BY source
    ''').fetchall()
    
    conn.close()
    
    return jsonify({
        'today': today_count,
        'week': week_count,
        'month': month_count,
        'total': total_count,
        'deep': deep_count,
        'sources': [dict(row) for row in source_stats]
    })

@screen_bp.route('/api/screen/trend')
def screen_trend():
    """获取趋势数据"""
    conn = get_db_connection()
    
    # 最近7天每日采集趋势
    trend_data = conn.execute('''
        SELECT 
            DATE(collect_time) as date,
            COUNT(*) as count
        FROM collected_data
        WHERE DATE(collect_time) >= DATE('now', '-7 days')
        GROUP BY DATE(collect_time)
        ORDER BY date
    ''').fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in trend_data])

@screen_bp.route('/api/screen/keywords')
def screen_keywords():
    """获取热门关键词（基于标题分词）"""
    conn = get_db_connection()
    
    # 获取最近的标题，简单统计高频词
    titles = conn.execute('''
        SELECT title FROM collected_data 
        WHERE DATE(collect_time) >= DATE('now', '-7 days')
        LIMIT 200
    ''').fetchall()
    
    conn.close()
    
    # 简单的关键词提取（实际项目可用jieba分词）
    keyword_counts = {}
    for row in titles:
        title = row['title'] or ''
        # 简单按长度提取关键词
        words = [title[i:i+4] for i in range(len(title)-3)]
        for word in words[:5]:
            if len(word) >= 3:
                keyword_counts[word] = keyword_counts.get(word, 0) + 1
    
    # 排序取前10
    top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return jsonify([{'keyword': k, 'count': v} for k, v in top_keywords])

@screen_bp.route('/api/screen/deep_rank')
def screen_deep_rank():
    """深度采集排行"""
    conn = get_db_connection()
    
    deep_rank = conn.execute('''
        SELECT 
            c.title,
            c.source,
            d.summary,
            c.collect_time
        FROM collected_data c
        JOIN deep_collected_data d ON c.id = d.source_id
        WHERE c.deep_status = 2
        ORDER BY c.collect_time DESC
        LIMIT 5
    ''').fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in deep_rank])
