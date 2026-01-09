import sqlite3
import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from openai import OpenAI
import time

class DeepCrawlService:
    def __init__(self, db_path):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_ai_model(self, model_id=None):
        conn = self._get_connection()
        if model_id:
            model = conn.execute('SELECT * FROM ai_models WHERE id = ?', (model_id,)).fetchone()
        else:
            model = conn.execute('SELECT * FROM ai_models WHERE is_active = 1 LIMIT 1').fetchone()
        conn.close()
        return dict(model) if model else None

    def get_deep_data(self, keyword=None, page=1, per_page=10):
        conn = self._get_connection()
        where_clause = ""
        params = []
        if keyword:
            where_clause = " WHERE d.title LIKE ? OR d.content LIKE ? OR d.url LIKE ?"
            like_val = f"%{keyword}%"
            params.extend([like_val, like_val, like_val])
        
        count_query = f"SELECT COUNT(*) FROM deep_collected_data d {where_clause}"
        total = conn.execute(count_query, params).fetchone()[0]
        
        query = f"""
            SELECT d.*, c.title as source_title 
            FROM deep_collected_data d 
            LEFT JOIN collected_data c ON d.source_id = c.id 
            {where_clause}
            ORDER BY d.collect_time DESC LIMIT ? OFFSET ?
        """
        params.extend([per_page, (page - 1) * per_page])
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return [dict(row) for row in rows], total

    def delete_deep_data(self, data_id):
        conn = self._get_connection()
        row = conn.execute('SELECT source_id FROM deep_collected_data WHERE id = ?', (data_id,)).fetchone()
        if row:
            source_id = row['source_id']
            conn.execute('DELETE FROM deep_collected_data WHERE id = ?', (data_id,))
            conn.execute('UPDATE collected_data SET deep_status = 0 WHERE id = ?', (source_id,))
        conn.commit()
        conn.close()

    def batch_delete_deep_data(self, ids):
        if not ids: return
        conn = self._get_connection()
        placeholders = ','.join(['?'] * len(ids))
        rows = conn.execute(f'SELECT source_id FROM deep_collected_data WHERE id IN ({placeholders})', ids).fetchall()
        source_ids = [row['source_id'] for row in rows if row['source_id']]
        
        conn.execute(f'DELETE FROM deep_collected_data WHERE id IN ({placeholders})', ids)
        
        if source_ids:
            s_placeholders = ','.join(['?'] * len(source_ids))
            conn.execute(f'UPDATE collected_data SET deep_status = 0 WHERE id IN ({s_placeholders})', source_ids)
            
        conn.commit()
        conn.close()

    def update_deep_data(self, data_id, title, content, summary, structured_data):
        conn = self._get_connection()
        conn.execute('''
            UPDATE deep_collected_data 
            SET title = ?, content = ?, summary = ?, structured_data = ?
            WHERE id = ?
        ''', (title, content, summary, structured_data, data_id))
        conn.commit()
        conn.close()

    def run_deep_crawl_task(self, source_ids, model_id):
        """生成器，用于 SSE 输出进度"""
        model = self.get_ai_model(model_id)
        if not model:
            yield f"data: {json.dumps({'error': '未找到可用的 AI 模型'})}\n\n"
            return

        total = len(source_ids)
        success_count = 0
        fail_count = 0

        conn = self._get_connection()
        
        for i, sid in enumerate(source_ids):
            # 获取源数据
            source = conn.execute('SELECT * FROM collected_data WHERE id = ?', (sid,)).fetchone()
            if not source:
                continue
            
            url = source['url']
            progress = int((i / total) * 100)
            
            yield f"data: {json.dumps({'status': 'processing', 'current': i+1, 'total': total, 'progress': progress, 'title': source['title']})}\n\n"
            
            # 更新状态为“正在采集”
            conn.execute('UPDATE collected_data SET deep_status = 1 WHERE id = ?', (sid,))
            conn.commit()

            try:
                # 深度采集阶段 1: 网页爬取 (CrawlAI 核心思路：极速获取干净 Markdown/Text)
                # 由于环境限制，我们使用 requests + bs4 模拟 CrawlAI 的获取过程
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                req_resp = requests.get(url, headers=headers, timeout=15)
                req_resp.encoding = req_resp.apparent_encoding
                soup = BeautifulSoup(req_resp.text, 'html.parser')
                
                # 简单清洗
                for s in soup(['script', 'style']): s.decompose()
                main_text = soup.get_text(separator='\n', strip=True)
                # 截断太长的文本防止 token 溢出
                clean_text = main_text[:4000] 

                # 深度采集阶段 2: AI 智能解析与提炼
                client = OpenAI(api_key=model['api_key'], base_url=model['api_url'])
                ai_prompt = f"""
                你是一个资深的数据分析专家。请根据以下网页内容，提取核心信息。
                要求输出 JSON 格式，包含以下字段：
                - title: 文章标题
                - summary: 50字以内的核心摘要
                - key_points: 列表，包含3-5个关键点
                - category: 信息分类（如：政策、新闻、招标、公告等）
                - sentiment: 情感倾向（正面/中性/负面）
                
                网页内容：
                {clean_text}
                """
                
                ai_resp = client.chat.completions.create(
                    model=model['model_name'],
                    messages=[
                        {"role": "system", "content": "你是一个专业的数据处理助手，只输出 JSON。"},
                        {"role": "user", "content": ai_prompt}
                    ],
                    response_format={"type": "json_object"} if "DeepSeek" in model['model_name'] or "gpt-4" in model['model_name'] else None
                )
                
                analysis_str = ai_resp.choices[0].message.content
                analysis = json.loads(analysis_str)
                
                # 保存到深度采集表
                # 使用 REPLACE INTO 或检查是否存在
                conn.execute('''
                    INSERT INTO deep_collected_data (source_id, url, title, content, summary, structured_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    summary=excluded.summary,
                    structured_data=excluded.structured_data,
                    collect_time=CURRENT_TIMESTAMP
                ''', (
                    sid, url, 
                    analysis.get('title', source['title']), 
                    clean_text[:2000],  # 保持内容精简
                    analysis.get('summary', ''),
                    json.dumps(analysis, ensure_ascii=False)
                ))
                
                # 记录 Token 消耗
                if hasattr(ai_resp, 'usage') and ai_resp.usage:
                    # 我们需要一个 AIService 的实例来记录，这里简单直接写
                    conn.execute('''
                        INSERT INTO token_usage (model_id, prompt_tokens, completion_tokens, total_tokens, task_type)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (model['id'], ai_resp.usage.prompt_tokens, ai_resp.usage.completion_tokens, ai_resp.usage.total_tokens, "深度采集分析"))

                # 更新状态为“成功”
                conn.execute('UPDATE collected_data SET deep_status = 2 WHERE id = ?', (sid,))
                conn.commit()
                success_count += 1
                
            except Exception as e:
                print(f"Deep crawl failed for {url}: {e}")
                conn.execute('UPDATE collected_data SET deep_status = 3 WHERE id = ?', (sid,))
                conn.commit()
                fail_count += 1

        conn.close()
        yield f"data: {json.dumps({'status': 'completed', 'success': success_count, 'fail': fail_count, 'total': total})}\n\n"
