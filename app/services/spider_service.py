import sqlite3
import os
import sys
import json
from datetime import datetime

# Import the BaiduSpider from the dist directory
# We need to add the project root to sys.path to import from dist
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from dist.baidusearch.search_cli import BaiduSpider

class SpiderService:
    def __init__(self, db_path):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_crawlers(self):
        conn = self._get_connection()
        crawlers = conn.execute('SELECT * FROM crawlers ORDER BY create_time DESC').fetchall()
        conn.close()
        return [dict(row) for row in crawlers]

    def add_crawler(self, name, spider_type, script_path=None, config=None, description=None):
        conn = self._get_connection()
        conn.execute('''
            INSERT INTO crawlers (name, type, script_path, config, description, status) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, spider_type, script_path, config, description, '可用'))
        conn.commit()
        conn.close()

    def delete_crawler(self, crawler_id):
        conn = self._get_connection()
        conn.execute('DELETE FROM crawlers WHERE id = ?', (crawler_id,))
        conn.commit()
        conn.close()

    def run_baidu_spider(self, crawler_id, keyword, limit=10):
        # Update status to running
        conn = self._get_connection()
        conn.execute('UPDATE crawlers SET status = ?, last_run = ? WHERE id = ?', ('运行中', datetime.now(), crawler_id))
        conn.commit()
        
        try:
            spider = BaiduSpider()
            results = spider.search(keyword, limit=limit)
            
            # Save results to collected_data
            for item in results:
                conn.execute('''
                    INSERT INTO collected_data (title, url, description, source)
                    VALUES (?, ?, ?, ?)
                ''', (item['title'], item['url'], item['description'], item['source']))
            
            # Update status back to idle
            conn.execute('UPDATE crawlers SET status = ? WHERE id = ?', ('可用', crawler_id))
            
            # Update system stats (increment total data)
            current_stats = conn.execute('SELECT metric_value FROM system_stats WHERE metric_name = ?', ('total_data',)).fetchone()
            if current_stats:
                try:
                    # Remove commas for calculation
                    current_val = int(current_stats['metric_value'].replace(',', ''))
                    new_val = current_val + len(results)
                    # Format back with commas
                    formatted_val = "{:,}".format(new_val)
                    conn.execute('UPDATE system_stats SET metric_value = ? WHERE metric_name = ?', (formatted_val, 'total_data'))
                except:
                    pass

            conn.commit()
            return len(results)
        except Exception as e:
            conn.execute('UPDATE crawlers SET status = ? WHERE id = ?', ('异常', crawler_id))
            conn.commit()
            raise e
        finally:
            conn.close()

    def get_collected_data(self, keyword=None, page=1, per_page=10):
        conn = self._get_connection()
        query_base = """
            FROM collected_data c 
            LEFT JOIN deep_collected_data d ON c.id = d.source_id
        """
        where_clause = ""
        params = []
        
        if keyword:
            where_clause = " WHERE c.title LIKE ? OR c.description LIKE ? OR c.url LIKE ?"
            like_val = f"%{keyword}%"
            params.extend([like_val, like_val, like_val])
            
        # Get total count
        count_query = f"SELECT COUNT(*) {query_base} {where_clause}"
        total_count = conn.execute(count_query, params).fetchone()[0]
        
        query = f"SELECT c.*, d.id as deep_data_id {query_base} {where_clause} ORDER BY c.collect_time DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        data = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in data], total_count

    def delete_data(self, data_id):
        conn = self._get_connection()
        conn.execute('DELETE FROM collected_data WHERE id = ?', (data_id,))
        conn.commit()
        conn.close()

    def batch_delete_data(self, data_ids):
        if not data_ids:
            return
        conn = self._get_connection()
        placeholders = ','.join(['?'] * len(data_ids))
        conn.execute(f'DELETE FROM collected_data WHERE id IN ({placeholders})', data_ids)
        conn.commit()
        conn.close()
