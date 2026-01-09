# AI智能政企瞭望舆情数据采集与分析系统

这是一套基于 Python Flask 开发的 AI 驱动型 Web 应用系统，专注于政企舆情数据的自动化采集、存储及智能化深度分析。

## 🚀 技术栈
- **后端**: Python 3.x, Flask (Web 框架)
- **前端**: HTML5, Vanilla JS, CSS3 (现代美学设计)
- **数据库**: SQLite3 (本地轻量级持久化)
- **实时通信**: WebSocket / SSE (用于爬虫日志和 AI 生成进度同步)
- **AI 驱动**: 集成了 DeepSeek 等大语言模型 API，支持内容的自动化摘要与结构化提取

## 📂 项目结构
```text
e:/2026年实训/day3/demo1/
├── app/                    # 核心应用目录
│   ├── routes/             # 路由定义 (视图逻辑)
│   ├── services/           # 业务逻辑 (如爬虫服务、AI 服务)
│   ├── templates/          # Jinja2 HTML 模板
│   ├── static/             # 静态资源 (CSS, JS, 图像)
│   └── __init__.py         # Flask App 工厂初始化
├── venv/                   # Python 虚拟环境
├── init_db.py              # 数据库初始化脚本
├── run.py                  # 系统启动入口
├── requirements.txt        # 项目依赖列表
└── data.db                 # SQLite 数据库文件 (运行后生成)
```

## 🛠️ 安装与运行指南

### 1. 克隆与环境准备
确保已安装 Python 3.8+。建议在虚拟环境中操作：
```powershell
# 激活虚拟环境 (Windows)
.\venv\Scripts\Activate.ps1
```

### 2. 安装依赖
```powershell
pip install -r requirements.txt
```

### 3. 初始化数据库
在系统首次运行前，必须执行此脚本来创建数据表并填充演示数据：
```powershell
python init_db.py
```
*注：此操作会生成默认管理员账号 `admin` / `admin123`。*

### 4. 启动系统
执行主入口程序：
```powershell
python run.py
```
启动后，在浏览器访问：[http://127.0.0.1:5000](http://127.0.0.1:5000)

## 💡 功能亮点

### 📊 后台主页 (Dashboard)
- 采用 ECharts 渲染的实时数据统计图表。
- 监控采集总量、AI 引擎状态及系统负载。

### 🕷️ 采集与爬虫管理
- 支持定点数据源抓取。
- 实时显示爬虫进度与抓取日志。

### 🤖 AI 深采管理 (Deep Collection)
- 利用大模型对长篇文章进行**秒级摘要**。
- 自动提取政企关心的关键字段（如：主体单位、影响级别、事件分类）。

### ⚙️ AI 模型配置
- 支持自定义 API URL、API Key 以及 System Prompt。
- 内置对 DeepSeek 系列模型的深度适配。

## 🔐 默认账号信息
| 角色 | 用户名 | 密码 |
| :--- | :--- | :--- |
| **超级管理员** | `admin` | `admin123` |

## ⚠️ 注意事项
1. **API Key**: 使用深度采集功能前，请在“AI模型管理”中填入有效的 API Key。
2. **网络环境**: 爬虫任务需要能够正常访问互联网。
3. **线程安全**: 系统在后台执行任务时使用 SSE 推送消息，请确保浏览器无跨域限制。

---
*Developed as part of the 2026 Practical Training Program.*
