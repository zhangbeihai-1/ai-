import sqlite3
import os

DB_PATH = 'data.db'

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 检查 collected_data 是否有 deep_status 列
    cursor.execute("PRAGMA table_info(collected_data)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'deep_status' not in columns:
        print("Adding 'deep_status' column to 'collected_data'...")
        cursor.execute("ALTER TABLE collected_data ADD COLUMN deep_status INTEGER DEFAULT 0")
        conn.commit()
    
    # 2. 创建 deep_collected_data 表
    print("Creating 'deep_collected_data' table if not exists...")
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
    
    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == '__main__':
    migrate()
