# dist/baidusearch/search_cli.py
import requests
from bs4 import BeautifulSoup
import argparse
import time
import random
import json
import sys

class BaiduSpider:
    """百度网页搜索爬虫"""
    def __init__(self):
        self.base_url = "https://www.baidu.com/s"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Connection": "keep-alive",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }

    def get_real_url(self, raw_url):
        if not raw_url.startswith("http"):
            return raw_url
        try:
            res = requests.head(raw_url, headers=self.headers, allow_redirects=False, timeout=5)
            if res.status_code in [301, 302]:
                return res.headers.get("Location", raw_url)
        except Exception:
            pass
        return raw_url

    def search(self, keyword, start_page=1, limit=5):
        page = start_page
        count = 0
        while count < limit:
            pn = (page - 1) * 10
            params = {"wd": keyword, "pn": pn}
            try:
                response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
                if response.status_code != 200:
                    break
                soup = BeautifulSoup(response.text, "html.parser")
                items = soup.select("div.c-container")
                if not items:
                    break
                for item in items:
                    if count >= limit: break
                    title_tag = item.select_one("h3 a")
                    if not title_tag: continue
                    title = title_tag.get_text().strip()
                    link = title_tag.get("href")
                    img_url = ""
                    img_tag = item.select_one("img.c-img") or item.select_one(".c-span6 img") or item.select_one(".c-span3 img")
                    if img_tag:
                        img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                        if img_url.startswith("//"): img_url = "https:" + img_url
                    desc_tag = item.select_one("div.c-abstract") or item.select_one(".content-right_8Zs40")
                    description = desc_tag.get_text().strip() if desc_tag else "暂无简介"
                    real_url = self.get_real_url(link)
                    yield {
                        "rank": count + 1,
                        "title": title,
                        "url": real_url,
                        "img": img_url,
                        "description": description,
                        "source": "baidu_search",
                        "time": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    count += 1
                page += 1
                time.sleep(random.uniform(0.5, 1.0))
            except Exception as e:
                print(f"[Error] Baidu Search Error: {e}", file=sys.stderr)
                break

class BaiduNewsSpider:
    """百度新闻爬虫"""
    def __init__(self):
        self.base_url = "https://www.baidu.com/s"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

    def search(self, keyword, limit=10):
        # rtt=1: 按时间排序, rtt=4: 按相关性排序
        params = {"tn": "news", "wd": keyword, "rtt": 1}
        count = 0
        try:
            res = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            if res.status_code != 200: return
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.select(".result-op.news")
            for item in items:
                if count >= limit: break
                title_tag = item.select_one("h3 a")
                if not title_tag: continue
                title = title_tag.get_text().strip()
                url = title_tag.get("href")
                source_tag = item.select_one(".c-color-gray.c-font-normal")
                source_name = source_tag.get_text().strip() if source_tag else "百度新闻"
                desc_tag = item.select_one(".c-font-normal.c-color-text")
                description = desc_tag.get_text().strip() if desc_tag else "点击查看详情"
                img_tag = item.select_one(".c-img img")
                img_url = ""
                if img_tag:
                    img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                    if img_url.startswith("//"): img_url = "https:" + img_url
                
                yield {
                    "rank": count + 1,
                    "title": title,
                    "url": url,
                    "img": img_url,
                    "description": f"[{source_name}] {description}",
                    "source": "baidu_news",
                    "time": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                count += 1
        except Exception as e:
            print(f"[Error] Baidu News Error: {e}", file=sys.stderr)

class SoSpider:
    """360搜索爬虫"""
    def __init__(self):
        self.base_url = "https://www.so.com/s"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

    def search(self, keyword, limit=10):
        params = {"q": keyword}
        try:
            res = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
            if res.status_code != 200: return
            soup = BeautifulSoup(res.text, "html.parser")
            items = soup.select(".res-list")
            count = 0
            for item in items:
                if count >= limit: break
                title_tag = item.select_one("h3 a")
                if not title_tag: continue
                title = title_tag.get_text().strip()
                url = title_tag.get("href")
                desc_tag = item.select_one(".res-desc") or item.select_one(".res-rich")
                description = desc_tag.get_text().strip() if desc_tag else "查看更多内容..."
                img_tag = item.select_one(".res-img img") or item.select_one("img")
                img_url = ""
                if img_tag:
                    img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                    if img_url.startswith("//"): img_url = "https:" + img_url
                yield {
                    "rank": count + 1,
                    "title": title,
                    "url": url,
                    "img": img_url,
                    "description": description,
                    "source": "360_search",
                    "time": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                count += 1
        except Exception as e:
            print(f"[Error] 360 Search Error: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="政企信息采集器")
    parser.add_argument("--wd", type=str, required=True)
    parser.add_argument("--type", type=str, default="baidu", choices=["baidu", "baidu_news", "360"])
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    
    if args.type == "baidu":
        spider = BaiduSpider()
    elif args.type == "baidu_news":
        spider = BaiduNewsSpider()
    else:
        spider = SoSpider()
        
    results = list(spider.search(args.wd, limit=args.limit))
    print(json.dumps(results, ensure_ascii=False, indent=4))

if __name__ == "__main__":
    main()
