import sqlite3
import os
from openai import OpenAI

class AIService:
    def __init__(self, db_path='data.db'):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_models(self):
        conn = self._get_connection()
        try:
            # 获取模型列表及其累计 Token
            query = '''
                SELECT m.*, 
                IFNULL(SUM(u.total_tokens), 0) as used_tokens
                FROM ai_models m
                LEFT JOIN token_usage u ON m.id = u.model_id
                GROUP BY m.id
                ORDER BY m.create_time DESC
            '''
            models = conn.execute(query).fetchall()
            return [dict(row) for row in models]
        finally:
            conn.close()

    def add_model(self, name, api_url, api_key, model_name, system_prompt):
        conn = self._get_connection()
        try:
            conn.execute('''
                INSERT INTO ai_models (name, api_url, api_key, model_name, system_prompt)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, api_url, api_key, model_name, system_prompt))
            conn.commit()
        finally:
            conn.close()

    def get_model_by_id(self, model_id):
        conn = self._get_connection()
        try:
            model = conn.execute('SELECT * FROM ai_models WHERE id = ?', (model_id,)).fetchone()
            return dict(model) if model else None
        finally:
            conn.close()

    def log_token_usage(self, model_id, prompt_tokens, completion_tokens, task_type):
        conn = self._get_connection()
        try:
            total = prompt_tokens + completion_tokens
            conn.execute('''
                INSERT INTO token_usage (model_id, prompt_tokens, completion_tokens, total_tokens, task_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (model_id, prompt_tokens, completion_tokens, total, task_type))
            conn.commit()
        finally:
            conn.close()

    def chat_test(self, model_id, message):
        # 此方法保留用于非流式测试
        model = self.get_model_by_id(model_id)
        if not model:
            return {"error": "Model not found"}
        try:
            client = OpenAI(api_key=model['api_key'], base_url=model['api_url'])
            response = client.chat.completions.create(
                model=model['model_name'],
                messages=[
                    {"role": "system", "content": model['system_prompt']},
                    {"role": "user", "content": message}
                ],
                temperature=0.7
            )
            content = response.choices[0].message.content
            self.log_token_usage(model_id, response.usage.prompt_tokens, response.usage.completion_tokens, "测试对话")
            return {
                "content": content,
                "usage": {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                    "total": response.usage.total_tokens
                }
            }
        except Exception as e:
            return {"error": str(e)}

    def chat_stream(self, model_id, message):
        """SSE 流式对话实现"""
        model = self.get_model_by_id(model_id)
        if not model:
            yield "data: {\"error\": \"模型未找到\"}\n\n"
            return

        try:
            client = OpenAI(api_key=model['api_key'], base_url=model['api_url'])
            response = client.chat.completions.create(
                model=model['model_name'],
                messages=[
                    {"role": "system", "content": model['system_prompt']},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                stream=True,
                stream_options={"include_usage": True} # 一些 provider 支持在流末尾返回使用量
            )

            full_content = ""
            usage = None
            
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        content = delta.content
                        full_content += content
                        yield f"data: {content}\n\n"
                
                # 处理流式结尾的 usage
                if hasattr(chunk, 'usage') and chunk.usage:
                    usage = chunk.usage

            # 如果 provider 返回了 usage，则记录入库
            if usage:
                self.log_token_usage(
                    model_id, 
                    usage.prompt_tokens, 
                    usage.completion_tokens, 
                    "流式测试对话"
                )
            else:
                # 如果没有 usage (部分 provider 不支持 stream_options)，则估算或跳过
                # 这里简单处理：如果没有返回 usage，按字符数粗略估算 (仅作兜底展示，不严谨)
                estimated_completion = len(full_content) // 2
                self.log_token_usage(model_id, len(message)//2, estimated_completion, "流式测试对话(估算)")

        except Exception as e:
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

    def update_model(self, model_id, name, api_url, api_key, model_name, system_prompt):
        conn = self._get_connection()
        try:
            conn.execute('''
                UPDATE ai_models 
                SET name = ?, api_url = ?, api_key = ?, model_name = ?, system_prompt = ?
                WHERE id = ?
            ''', (name, api_url, api_key, model_name, system_prompt, model_id))
            conn.commit()
        finally:
            conn.close()

    def delete_model(self, model_id):
        conn = self._get_connection()
        try:
            conn.execute('DELETE FROM ai_models WHERE id = ?', (model_id,))
            conn.execute('DELETE FROM token_usage WHERE model_id = ?', (model_id,))
            conn.commit()
        finally:
            conn.close()

    def _execute_sql(self, sql):
        """执行 SQL 并返回结果列表 (仅限查询)"""
        if not sql.strip().upper().startswith('SELECT'):
             return {"error": "只允许执行 SELECT 查询语句以确保数据安全。"}
        
        conn = self._get_connection()
        try:
            cursor = conn.execute(sql)
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(row))
            return results
        except Exception as e:
            return {"error": str(e)}
        finally:
            conn.close()

    def chat_analysis_stream(self, model_id, message, conversation_id=None):
        """增强版流式对话：支持工具调用、数据库交互与多会话保存"""
        model = self.get_model_by_id(model_id)
        if not model:
            yield "data: {\"error\": \"模型未找到\"}\n\n"
            return

        # 1. 完善系统提示词，告知数据库 Schema (强制 SQLite 语法)
        db_context = f"""
你是一个专业的数据分析助手（底层数据库由 SQLite 3 驱动）。
你可以访问数据库中的以下两张表：

1. `collected_data` (外层采集表):
   - id: 唯一标识
   - title: 标题
   - url: 链接
   - description: 描述
   - source: 来源 (baidu_news, baidu_search)
   - collect_time: 采集日期(TIMESTAMP)
   - deep_status: 深度采集状态 (0: 未开始, 2: 成功)

2. `deep_collected_data` (深度详情表):
   - id: 唯一标识
   - source_id: 关联 collected_data 的 id
   - title: 详情标题
   - content: 网页全文内容
   - summary: AI 总结信息
   - collect_time: 采集日期(TIMESTAMP)

你的任务要求：
1. **必须使用 SQLite 语法**：例如日期查询使用 `date('now', '-3 days')` 而非 `DATE_SUB`。
2. **工具优先级**：回答用户前，如果需要数据，先使用 `execute_sql` 工具查询。
3. **输出规范**：
   - 严禁将原始 SQL 语句直接输出给普通用户（除非用户明确要求查看 SQL）。
   - 如果你要展示你的思维过程，请将其包裹在 `<thought>` 标签中。
   - 报表必须使用规范的 ````json_chart ... ```` 块。
"""

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "execute_sql",
                    "description": "执行 SQL SELECT 语句以查询数据库。支持聚合统计如 COUNT, GROUP BY 等。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {"type": "string", "description": "完整的 SQL SELECT 语句。"}
                        },
                        "required": ["sql"]
                    }
                }
            }
        ]

        full_raw_response = ""
        try:
            print(f"[AI Service] Starting chat_analysis_stream for conversation_id={conversation_id}")
            print(f"[AI Service] User message: {message[:100]}...")
            
            client = OpenAI(api_key=model['api_key'], base_url=model['api_url'])
            
            messages = [
                {"role": "system", "content": db_context},
                {"role": "user", "content": message}
            ]

            # 第一次调用：询问是否需要工具 (调低温度确保 SQL 准确性)
            print("[AI Service] Calling model with tool support...")
            response = client.chat.completions.create(
                model=model['model_name'],
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.1
            )

            res_msg = response.choices[0].message
            tool_calls = res_msg.tool_calls
            print(f"[AI Service] Tool calls detected: {tool_calls is not None and len(tool_calls) > 0}")

            if tool_calls:
                messages.append(res_msg)
                for tc in tool_calls:
                    if tc.function.name == "execute_sql":
                        import json
                        args = json.loads(tc.function.arguments)
                        sql_query = args.get('sql')
                        print(f"[AI Service] SQL Query: {sql_query}")
                        
                        # 记录到 raw_content 用于数据库保存（不发送给前端）
                        call_marker = f"<|DSML|call:execute_sql({sql_query})|>"
                        full_raw_response += call_marker
                        # 不再 yield call_marker，因为会干扰前端渲染
                        
                        print("[AI Service] Executing SQL...")
                        
                        sql_result = self._execute_sql(sql_query)
                        print(f"[AI Service] SQL Result: {len(sql_result) if isinstance(sql_result, list) else 'error'} records")
                        
                        # 截断超大结果，防止 context 撑爆
                        if isinstance(sql_result, list) and len(sql_result) > 20:
                            sql_result = sql_result[:20]
                            sql_result.append({"warning": "结果过多，已截断显示前 20 条。"})
                        
                        res_str = json.dumps(sql_result, ensure_ascii=False)
                        print(f"[AI Service] Result JSON length: {len(res_str)} chars")
                        
                        messages.append({
                            "tool_call_id": tc.id,
                            "role": "tool",
                            "name": "execute_sql",
                            "content": res_str
                        })
                
                
                # 第二次调用：生成最终回复
                # 关键：明确告诉AI不要再输出任何技术标签
                print("[AI Service] Calling model for final response...")
                messages.append({
                    "role": "system",
                    "content": "你现在要生成最终的用户可读分析报告。重要：不要输出任何<|DSML|>、function_calls或其他技术标签，只输出纯文本的Markdown格式分析内容。"
                })
                
                final_res = client.chat.completions.create(
                    model=model['model_name'],
                    messages=messages,
                    stream=True,
                    temperature=0.7
                )
                
                chunk_count = 0
                for chunk in final_res:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_raw_response += content
                        yield f"data: {content}\n\n"
                        chunk_count += 1
                        if chunk_count % 10 == 0:
                            print(f"[AI Service] Streamed {chunk_count} chunks...")
                
                print(f"[AI Service] Streaming complete. Total chunks: {chunk_count}")
            else:
                print("[AI Service] No tool calls, direct response")
                # 没触发工具：如果第一次调用已经有内容了，直接输出
                if res_msg.content:
                    content = res_msg.content
                    full_raw_response += content
                    yield f"data: {content}\n\n"
                    print(f"[AI Service] Yielded direct content: {len(content)} chars")
                else:
                    # 彻底保底：如果没有内容也没工具，发起一个简单的流式流
                    print("[AI Service] Fallback: streaming without tools")
                    final_res = client.chat.completions.create(
                        model=model['model_name'],
                        messages=messages,
                        stream=True,
                        temperature=0.7
                    )
                    for chunk in final_res:
                        if chunk.choices and chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full_raw_response += content
                            yield f"data: {content}\n\n"

            # 保存到数据库
            if conversation_id:
                print(f"[AI Service] Saving to database. Response length: {len(full_raw_response)} chars")
                from app.routes.main_routes import get_db_connection
                conn = get_db_connection()
                conn.execute(
                    'INSERT INTO analysis_messages (conversation_id, role, content, raw_content) VALUES (?, ?, ?, ?)',
                    (conversation_id, 'assistant', full_raw_response, full_raw_response)
                )
                conn.commit()
                conn.close()
                print("[AI Service] Saved to database successfully")

        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            print(f"[AI Service ERROR] {error_msg}")
            yield f"data: 系统错误: {str(e)}\n\n"
        
        print("[AI Service] Sending [DONE] signal")
        yield "data: [DONE]\n\n"
