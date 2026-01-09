import sqlite3
import os

DB_PATH = 'data.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    ''')
    
    # Create system_stats table for dashboard
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_name TEXT UNIQUE NOT NULL,
        metric_value TEXT NOT NULL,
        update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create chart_acquisition table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chart_acquisition (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT NOT NULL,
        value INTEGER NOT NULL
    )
    ''')

    # Create chart_sentiment table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chart_sentiment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        value INTEGER NOT NULL,
        color TEXT NOT NULL
    )
    ''')

    # Create crawlers table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS crawlers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        script_path TEXT,
        config TEXT,
        description TEXT,
        status TEXT DEFAULT '可用',
        last_run TIMESTAMP,
        create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create collected_data table # 爬虫数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS collected_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        url TEXT NOT NULL UNIQUE,
        description TEXT,
        source TEXT,
        collect_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        deep_status INTEGER DEFAULT 0 -- 0: 未采集, 1: 正在采集, 2: 采集成功, 3: 采集失败
    )
    ''')

    # Create deep_collected_data table # 深度采集数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS deep_collected_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id INTEGER UNIQUE,
        url TEXT NOT NULL,
        title TEXT,
        content TEXT,
        summary TEXT,
        structured_data TEXT, -- JSON format
        collect_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (source_id) REFERENCES collected_data (id)
    )
    ''')

    # AI 模型管理表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ai_models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        api_url TEXT NOT NULL,
        api_key TEXT NOT NULL,
        model_name TEXT NOT NULL,
        system_prompt TEXT DEFAULT '你是一个专业的政企信息分析助手。',
        is_active INTEGER DEFAULT 1,
        create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Token 消耗记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS token_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id INTEGER,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        task_type TEXT,
        log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (model_id) REFERENCES ai_models (id)
    )
    ''')

    # AI 分析会话表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analysis_conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT DEFAULT '新会话',
        model_id INTEGER,
        create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (model_id) REFERENCES ai_models (id)
    )
    ''')

    # AI 分析消息明细表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analysis_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER,
        role TEXT NOT NULL, -- 'user' or 'assistant'
        content TEXT NOT NULL,
        raw_content TEXT, -- 存储带标签的原始文本以便重新渲染
        create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES analysis_conversations (id) ON DELETE CASCADE
    )
    ''')

    # Seed initial crawler
    cursor.execute('SELECT * FROM crawlers WHERE name = ?', ('百度搜索爬虫',))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO crawlers (name, type, status) VALUES (?, ?, ?)', ('百度搜索爬虫', 'baidu', '可用'))
    
    # Seed admin user if not exists
    cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', ('admin', 'admin123'))
        print("Admin user created: admin / admin123")
    
    # Seed initial AI model
    cursor.execute('SELECT id FROM ai_models WHERE name = ?', ('SiliconFlow-Model',))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO ai_models (name, api_url, api_key, model_name)
            VALUES (?, ?, ?, ?)
        ''', ('SiliconFlow-Model', 'https://api.siliconflow.cn/v1/', 'sk-wpbsxfzhkvdxuwckpexejmsjjdiwbunjbunllpqlptrpinxi', 'deepseek-ai/DeepSeek-V3.2'))
        print("Default AI model 'SiliconFlow-Model' (DeepSeek-V3.2) seeded.")

    # Seed initial stats
    stats = [
        ('total_data', '1,245,678'),
        ('total_spiders', '245'),
        ('ai_engine_status', '正常'),
        ('network_status', '良好'),
        ('system_uptime', '245天')
    ]
    for name, val in stats:
        cursor.execute('INSERT OR IGNORE INTO system_stats (metric_name, metric_value) VALUES (?, ?)', (name, val))

    # Seed acquisition chart data
    cursor.execute('SELECT COUNT(*) FROM chart_acquisition')
    if cursor.fetchone()[0] == 0:
        acquisition_data = [
            ('周一', 1200), ('周二', 1320), ('周三', 1010), 
            ('周四', 1340), ('周五', 900), ('周六', 2300), ('周日', 2100)
        ]
        cursor.executemany('INSERT INTO chart_acquisition (day, value) VALUES (?, ?)', acquisition_data)

    # Seed sentiment chart data
    cursor.execute('SELECT COUNT(*) FROM chart_sentiment')
    if cursor.fetchone()[0] == 0:
        sentiment_data = [
            ('正面', 1048, '#52C41A'), 
            ('中性', 735, '#165DFF'), 
            ('负面', 580, '#FF4D4F')
        ]
        cursor.executemany('INSERT INTO chart_sentiment (name, value, color) VALUES (?, ?, ?)', sentiment_data)
    
    conn.commit()
    conn.close()
    print("Database initialized and seeded successfully.")

if __name__ == '__main__':
    init_db()
