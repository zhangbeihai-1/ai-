import sqlite3
import os

db_path = 'data.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO collected_data (title, url, description, source) VALUES (?, ?, ?, ?)", 
                 ('成都理工大学2025年度十大科技新闻', 'https://news.cdut.edu.cn/info/1001/4567.htm', 
                  '成都理工大学在地球科学、核技术应用等领域取得重大突破。', 'baidu_news'))
    conn.execute("INSERT INTO collected_data (title, url, description, source) VALUES (?, ?, ?, ?)", 
                 ('成都理工大学位列全国高校百强', 'https://top.cdut.edu.cn/ranking', 
                  '在最新公布的大学排名中，成都理工大学综合实力稳步提升。', 'baidu_search'))
    conn.commit()
    conn.close()
    print("Test data inserted successfully.")
else:
    print("Database not found.")
