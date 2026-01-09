
import sqlite3

def update_db():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Update existing '百度搜索爬虫' to have a specific type or config if needed
    # But for simplicity, I'll just add the new ones.
    
    new_crawlers = [
        ('百度新闻爬虫', 'baidu_news', 'dist/baidusearch/search_cli.py', None, '专门用于采集百度新闻数据的爬虫'),
        ('360搜索爬虫', '360_search', 'dist/baidusearch/search_cli.py', None, '使用360搜索引擎进行的通用采集')
    ]
    
    for name, ctype, path, cfg, desc in new_crawlers:
        # Check if already exists
        cursor.execute('SELECT id FROM crawlers WHERE name = ?', (name,))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO crawlers (name, type, script_path, config, description, status)
                VALUES (?, ?, ?, ?, ?, '可用')
            ''', (name, ctype, path, cfg, desc))
            print(f"Added crawler: {name}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_db()
