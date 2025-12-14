# cronjob/get_hk_news.py
# 爬取港美股新闻定时任务，顺序执行版本

import os
import re
import time
import hashlib
from datetime import datetime
import requests
import openai
import numpy as np
from utils.save import save_news, initialize_database, save_news_embeddings, get_recent_news_with_embeddings, check_content_hashes, save_news_tags
from dotenv import load_dotenv
import sys
from bs4 import BeautifulSoup
from typing import Tuple, Optional, List, Dict
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 加载环境变量
load_dotenv(override=True)

# 配置参数 
CREATE_TITLE_MODEL = os.getenv("CREATE_TITLE_MODEL")
CREATE_TITLE_BASE_URL = os.getenv("CREATE_TITLE_BASE_URL")
CREATE_TITLE_API_KEY = os.getenv("CREATE_TITLE_API_KEY")

# 嵌入API配置
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")

# 去重参数
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", 0.9))
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", 5))

# 初始化OpenAI客户端
title_client = openai.OpenAI(api_key=CREATE_TITLE_API_KEY, base_url=CREATE_TITLE_BASE_URL)
embedding_client = openai.OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)

def generate_sign(ts: int, category: str) -> str:
    raw = f"app=CailianpressWeb&category={category}&lastTime={ts}&last_time={ts}&os=web&refresh_type=1&rn=20&sv=8.4.6"
    sha1_result = hashlib.sha1(raw.encode()).hexdigest()
    return hashlib.md5(sha1_result.encode()).hexdigest()

def format_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

# 使用API进行嵌入函数
def create_embedding(content: str, model: str = None):
    """
    使用OpenAI API生成文本嵌入向量
    """
    if model is None:
        model = EMBEDDING_MODEL
        
    try:
        # 处理文本长度，避免超过模型限制
        max_tokens = 8192  # 设置一个保守的限制，低于8192的上限
        
        # 文本过长时进行截断处理
        if len(content) > max_tokens * 3:  # 粗略估计：1个字符约占0.33个token           
            content = content[:max_tokens*2.8]  # 截断至约2.5倍token限制
            print(f"⚠️ 文本过长，已截断至约{len(content)}字符")
        
        # 直接调用同步API
        response = embedding_client.embeddings.create(
            input=content,
            model=model
        )
        # 获取嵌入向量
        embedding_vector = np.array(response.data[0].embedding)
        return embedding_vector
    except Exception as e:
        print(f"❗嵌入生成失败: {e}")
        return None

# 使用numpy计算余弦相似度
def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """
    计算两个向量之间的余弦相似度
    """
    if a is None or b is None:
        return 0.0
    
    # 计算余弦相似度：点积 / (向量a的模 * 向量b的模)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    return dot_product / (norm_a * norm_b)

def extract_news_link(url_or_schema):
    """从各种格式的URL或schema中提取新闻链接"""
    if not url_or_schema:
        return ""
    
    # 处理schema格式
    if 'schema' in url_or_schema or '&id=' in url_or_schema or 'id=' in url_or_schema:
        # 匹配形如 *id=xxx 的模式，其中*可以是share_id, shareid等
        match = re.search(r'(\w+id)=([A-Za-z0-9]+)', url_or_schema)
        if match:
            return f"https://www.cls.cn/detail/{match.group(2)}"
    
    # 处理普通shareurl
    # 匹配形如 /share/article/2040799 的模式
    match = re.search(r'/share/article/(\d+)', url_or_schema)
    if match:
        return f"https://www.cls.cn/detail/{match.group(1)}"
    
    return url_or_schema  # 如果无法提取ID，则返回原始URL或空字符串

# 添加在 extract_news_link 函数之后
def content_hash(text):
    """计算内容哈希值"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


# 添加日志控制函数
def log_verbose(message, verbose_only=False):
    """控制日志输出"""
    # 默认只输出重要信息，详细日志可选择性关闭
    if not verbose_only:
        print(message)

def crawl_content(url: str) -> Tuple[Optional[str], Optional[str]]:
    """爬取指定URL页面中的摘要和详细内容"""
    if not isinstance(url, str) or not url:
        return None, None
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
    }
    
    try:
        # 减少爬取日志，改为更简洁的输出
        log_verbose(f"🌐 爬取: {url}", verbose_only=True)
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            log_verbose(f"❌ 请求失败，状态码: {response.status_code}", verbose_only=True)
            return None, None
            
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 模糊匹配detail-brief
        brief_elem = None
        for elem in soup.find_all(class_=True):
            if "detail-brief" in ' '.join(elem.get('class', [])):
                brief_elem = elem
                break
        
        # 处理摘要内容 - 去除【】包裹的内容
        brief_content = None
        if brief_elem:
            brief_text = brief_elem.get_text(strip=True)
            # 去除【】包裹的内容
            brief_content = re.sub(r'【[^】]*】', '', brief_text).strip()
        
        # 模糊匹配detail-content
        content_elem = None
        for elem in soup.find_all(class_=True):
            if "detail-content" in ' '.join(elem.get('class', [])):
                content_elem = elem
                break
        
        # 处理详细内容
        content_text = None
        if content_elem:
            # 处理段落，忽略<strong>和<a>标签，但在每个<p>后添加换行符
            paragraphs = []
            for p in content_elem.find_all('p'):
                # 获取段落文本，忽略内部标签
                p_text = p.get_text(strip=True)
                # 去除【】包裹的内容
                p_text = re.sub(r'【[^】]*】', '', p_text).strip()
                if p_text:  # 只添加非空段落
                    paragraphs.append(p_text)
            
            # 使用换行符连接所有段落
            content_text = '\n'.join(paragraphs)
        
        # 简化成功日志
        if brief_content or content_text:
            log_verbose(f"✅ 爬取成功: {url}", verbose_only=True)
            
        return brief_content, content_text

    except Exception as e:
        log_verbose(f"❌ 爬取失败: {str(e)}", verbose_only=True)
        return None, None

def create_title(content: str) -> tuple:
    """
    从内容中提取标题或生成新标题，同时返回清理后的内容
    
    参数:
    - content: 原始内容文本
    
    返回:
    - (title, cleaned_content): 标题和清理后的内容
    """
    # 检查内容是否已包含【】格式的标题
    m = re.match(r"^【([^】]+)】(.*)", content)
    if m:
        title = m.group(1).strip()
        cleaned_content = m.group(2).strip()
        return title, cleaned_content
    
    # 如果没有现成标题，需要生成
    cleaned_content = content.strip()
    
    # 使用AI生成标题
    prompt = f"你是一个财经新闻标题生成器，我将给你一条财经新闻的内容，请你生成一个简洁、有信息量的中文标题，突出金融要点，不超过25个汉字。注意只需要输出标题内容，无需其他任何多余信息，不需要使用任何符号包裹。以下是新闻内容\n{cleaned_content}"
    try:
        # 直接调用同步API
        resp = title_client.chat.completions.create(
            model=CREATE_TITLE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=64
        )
        title = resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"❗标题生成失败: {e}")
        traceback.print_exc()
        title = f"{cleaned_content[:20]}"
        
    return title, cleaned_content

def analyze_news_content(content, title=None, max_retries=3):
    """
    使用AI分析新闻内容，提取标签和摘要，支持失败重试
    
    参数:
    - content: 新闻内容
    - title: 可选的新闻标题
    - max_retries: 最大重试次数
    
    返回:
    - dict: 包含positive_tags, negative_tags, is_important, summary的字典
    """
    full_text = f"标题: {title}\n内容: {content}" if title else content
    
    prompt = f"""你一位金融新闻分析师，请你分析以下财经新闻内容，帮助我提取关键信息:
    
{full_text}

请以JSON格式返回以下信息:
1. positive_tags: 这条新闻对哪些股票板块/哪些行业是重大利好的？提供中文的标签列表，最多3个标签
2. negative_tags: 这条新闻对哪些板块/哪些行业是重大利空的？提供中文的标签列表，最多3个标签
3. is_important: 这是否是一条重大财经事件？(true/false)
4. summary: 用50个字以内总结这条新闻的要点

必须直接返回有效的JSON格式数据，不要有其他说明或任何前后缀。
无需使用```json```包裹，直接返回JSON
positive_tags与negative_tags是互斥的，如果有positive_tags那negative_tags就应该为空"""

    retries = 0
    while retries <= max_retries:
        try:
            # 每次重试时稍微调整温度参数
            temperature = 0.2 + (retries * 0.1)
            
            # 直接调用同步API
            resp = title_client.chat.completions.create(
                model=CREATE_TITLE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=256,
                response_format={"type": "json_object"}
            )
            
            # 解析JSON响应
            result_text = resp.choices[0].message.content.strip()
            try:
                import json
                result = json.loads(result_text)
                # 确保所有字段存在
                return {
                    'positive_tags': result.get('positive_tags', []),
                    'negative_tags': result.get('negative_tags', []),
                    'is_important': result.get('is_important', False),
                    'summary': result.get('summary', '')
                }
            except json.JSONDecodeError:
                # 尝试从```json```标记中提取JSON
                json_pattern = r'```json\s*([\s\S]*?)\s*```'
                match = re.search(json_pattern, result_text)
                if match:
                    try:
                        # 提取JSON字符串并解析
                        json_str = match.group(1).strip()
                        print(f"🔍 从代码块中提取JSON: {json_str[:100]}...")
                        result = json.loads(json_str)
                        # 确保所有字段存在
                        return {
                            'positive_tags': result.get('positive_tags', []),
                            'negative_tags': result.get('negative_tags', []),
                            'is_important': result.get('is_important', False),
                            'summary': result.get('summary', '')
                        }
                    except json.JSONDecodeError:
                        print("❗ 从代码块提取的JSON仍然无效")
                
                if retries < max_retries:
                    retries += 1
                    print(f"❗ AI返回的JSON格式无效 (第{retries}次尝试)，进行重试...")
                    print(result_text)
                    # 增加提示的明确性
                    prompt += "\n\n请确保返回格式正确的JSON，不要有任何额外文本。"
                    continue
                else:
                    print(f"❗ AI返回的JSON格式无效，已达到最大重试次数 ({max_retries})")
                    print(result_text)
                    return {
                        'positive_tags': [],
                        'negative_tags': [],
                        'is_important': False,
                        'summary': content[:50] + ('...' if len(content) > 50 else '')
                    }
        except Exception as e:
            if retries < max_retries:
                retries += 1
                print(f"❗ 新闻内容分析失败 (第{retries}次尝试): {e}，进行重试...")
                # 短暂等待后重试
                time.sleep(1)
                continue
            else:
                print(f"❗ 新闻内容分析失败，已达到最大重试次数 ({max_retries}): {e}")
                # 返回默认值
                return {
                    'positive_tags': [],
                    'negative_tags': [],
                    'is_important': False,
                    'summary': content[:50] + ('...' if len(content) > 50 else '')
                }

def fetch_and_process(category: str = "hk_us"):
    ts = int(time.time())
    sign = generate_sign(ts, category)

    url = "https://www.cls.cn/v1/roll/get_roll_list"
    params = {
        "app": "CailianpressWeb",
        "category": category,
        "last_time": ts,
        "lastTime": ts,
        "os": "web",
        "refresh_type": "1",
        "rn": "20",
        "sv": "8.4.6",
        "sign": sign
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.cls.cn/telegraph"
    }

    # 简化请求参数日志
    log_verbose(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 获取{category}类别新闻...")
    
    result = {
        "success": True,
        "new_count": 0,
        "duplicate_count": 0,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("errno") != 0:
            log_verbose(f"❌ 接口返回错误：{data.get('msg')}")
            return

        raw_list = data["data"]["roll_data"]
        raw_list = raw_list[:5]  # 限制为20条新闻

        # 确定当前新闻类别
        code = "cn" if category == "watch" else category
        
        # 预处理：计算内容哈希并检查是否已存在
        items = []
        content_hashes = []
        for news in raw_list:
            content = news.get("content", "").strip()
            m = re.match(r"^【([^】]+)】(.*)", content)
            cleaned = m.group(2).strip() if m else content
            hash_value = content_hash(cleaned)
            content_hashes.append(hash_value)
            items.append((news, cleaned, hash_value))
        
        # 批量检查哪些内容哈希已存在
        existing_hashes = check_content_hashes(content_hashes)
        
        # 简化哈希检查日志
        duplicate_by_hash = len(existing_hashes)
        if duplicate_by_hash > 0:
            log_verbose(f"哈希检查: {duplicate_by_hash}/{len(raw_list)}条新闻已存在")
        
        # 过滤掉已存在的新闻
        items_to_process = [(news, cleaned) for news, cleaned, hash_value in items if hash_value not in existing_hashes]
        
        if not items_to_process:
            log_verbose("所有新闻均已存在，无需处理")
            result["duplicate_count"] = len(raw_list)
            return result
        
        log_verbose(f"处理 {len(items_to_process)} 条新闻...")
        
        # 仅获取相同类别的最近新闻用于比较
        window_size = int(os.getenv("WINDOW_SIZE", 5))  # 从环境变量读取窗口大小，默认为5
        print(f"🔍 正在加载 {code} 类别的最近 {window_size} 条新闻")
        
        existing_news = get_recent_news_with_embeddings(EMBEDDING_MODEL, code, limit=window_size)
        
        # 提取已有的嵌入向量
        existing_embeddings = []
        news_without_embeddings = []
        
        for news in existing_news:
            if news['embedding'] is not None:
                existing_embeddings.append((news['id'], news['embedding']))
            else:
                news_without_embeddings.append(news)
        
        print(f"📊 已找到 {len(existing_embeddings)} 条带嵌入的新闻和 {len(news_without_embeddings)} 条无嵌入的新闻")
        
        # 为没有嵌入的新闻顺序计算嵌入
        if news_without_embeddings:
            print(f"🔄 正在为 {len(news_without_embeddings)} 条新闻顺序计算嵌入")
            
            embeddings_to_save = []
            for news in news_without_embeddings:
                emb = create_embedding(news['content'], EMBEDDING_MODEL)
                if emb is not None:
                    existing_embeddings.append((news['id'], emb))
                    embeddings_to_save.append({
                        'news_id': news['id'],
                        'embedding_vector': emb,
                        'model_name': EMBEDDING_MODEL
                    })
            
            # 保存新计算的嵌入
            if embeddings_to_save:
                save_news_embeddings(embeddings_to_save)

        # 顺序爬取内容和生成标题
        formatted_news = []
        embeddings_to_save = []
        new_count = 0
        duplicate_count = 0
        
        for idx, (news, cleaned) in enumerate(items_to_process, 1):
            # 爬取内容
            link = extract_news_link(news.get("shareurl", ""))
            if link:
                summary, full_content = crawl_content(link)
                if full_content:
                    cleaned = full_content
            
            # 生成标题
            title, cleaned_content = create_title(cleaned)
            
            # 计算嵌入
            print(f"🔄 正在为第 {idx} 条新闻计算嵌入")
            emb = create_embedding(cleaned_content, EMBEDDING_MODEL)
            
            if emb is None:
                continue

            # 检查是否与最近的新闻重复
            is_duplicate = False
            for news_id, old_emb in existing_embeddings:
                if cosine_sim(emb, old_emb) >= SIM_THRESHOLD:
                    print(f"🔄 发现重复新闻 (ID: {news_id}): {title}")
                    print(f"   📎 链接: {link}")
                    # 找到对应新闻对象
                    old_news = next((n for n in existing_news if n['id'] == news_id), None)
                    if old_news:
                        # 更新旧新闻
                        old_news["title"] = title
                        old_news["content"] = cleaned_content
                        old_news["ctime"] = format_ts(news.get("ctime", 0))
                        old_news["link"] = link
                        formatted_news.append(old_news)
                        
                        # 更新嵌入
                        embeddings_to_save.append({
                            'news_id': news_id,
                            'embedding_vector': emb,
                            'model_name': EMBEDDING_MODEL
                        })
                    is_duplicate = True
                    duplicate_count += 1
                    break

            if not is_duplicate:
                formatted_news.append({
                    "ctime": format_ts(news.get("ctime", 0)),
                    "title": title,
                    "content": cleaned_content,
                    "link": link,
                    "code": code
                })
                print(f"📌 新增 第{idx}条 | 🕒 {format_ts(news.get('ctime', 0))}")
                print(f"   📰 {title}")
                print(f"   📎 {link}")
                new_count += 1

        print(f"📊 处理结果: 新增 {new_count} 条新闻, 更新 {duplicate_count} 条重复新闻")
        
        # 保存新闻内容并获取结果（包含新闻ID）
        saved_results = save_news(formatted_news)
        
        if saved_results:
            # 为新增和更新的新闻准备嵌入数据
            news_embeddings = []
            
            # 处理更新的新闻嵌入
            for data in embeddings_to_save:
                # 检查此记录是否被跳过
                news_id = data['news_id']
                if news_id in saved_results and saved_results[news_id].get('skipped'):
                    continue
                news_embeddings.append(data)
            
            # 处理新增新闻的嵌入
            for news_item in formatted_news:
                for news_id, info in saved_results.items():
                    if info.get('is_new') and info['content'] == news_item['content'] and not info.get('skipped') and not info.get('existing'):
                        # 为新新闻重新计算嵌入
                        emb = create_embedding(news_item['content'], EMBEDDING_MODEL)
                        if emb is not None:
                            news_embeddings.append({
                                'news_id': news_id,
                                'embedding_vector': emb,
                                'model_name': EMBEDDING_MODEL
                            })
                        break
            
            # 保存所有嵌入（新增和更新）
            if news_embeddings:
                print(f"🔄 正在保存 {len(news_embeddings)} 条新闻嵌入")
                save_news_embeddings(news_embeddings)
                
            # 为新增的新闻生成并保存标签
            news_tags = []
            
            for news_id, info in saved_results.items():
                if info.get('is_new'):  # 只为新增的新闻生成标签
                    # 找到对应的新闻内容和标题
                    for news_item in formatted_news:
                        if news_item['content'] == info['content']:
                            # 分析新闻内容
                            print(f"🏷️ 正在分析新闻 {news_id} 的内容以生成标签...")
                            tag_info = analyze_news_content(news_item['content'], news_item['title'])
                            
                            # 添加新闻ID
                            tag_info['news_id'] = news_id
                            news_tags.append(tag_info)
                            break

            # 保存标签信息
            if news_tags:
                print(f"🔖 正在为 {len(news_tags)} 条新闻保存标签和摘要")
                save_news_tags(news_tags)
        
        # 更新返回值中的统计信息
        result["new_count"] = new_count
        result["duplicate_count"] = duplicate_count
        
        return result

    except Exception as e:
        print(f"❗请求失败：{e}")
        import traceback
        traceback.print_exc()
        result["success"] = False
        result["error"] = str(e)
        return result

def fetch_tops():
    """获取头条新闻"""
    base_url = "https://www.cls.cn/v3/depth/home/assembled/1000"
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "sv": "8.4.6",
    }

    # 头条API使用固定签名
    params["sign"] = "9f8797a1f4de66c2370f7a03990d2737"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.cls.cn/"
    }

    result = {
        "success": True,
        "new_count": 0,
        "duplicate_count": 0,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }

    try:
        resp = requests.get(base_url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("errno") != 0:
            print(f"❌ 头条接口返回错误：{data.get('msg')}")
            result["success"] = False
            result["error"] = data.get("msg")
            return result

        articles = data["data"].get("top_article", [])
        print(f"✅ 获取 {len(articles)} 条头条新闻：\n")

        formatted_news_list = []
        
        # 顺序处理每个链接
        for i, article in enumerate(articles, 1):
            schema = article.get("schema", "")
            link = extract_news_link(schema)
            
            # 提取标题和内容
            title = article.get("title", "").strip()
            content = article.get("brief", "").strip()
            
            # 顺序爬取内容
            summary, full_content = None, None
            if link:
                summary, full_content = crawl_content(link)
                if full_content:
                    content = full_content
        
            formatted_news_list.append({
                "ctime": format_ts(article["ctime"]),
                "title": title,
                "content": content,
                "link": link,
                "code": "top",  # 头条新闻使用"top"类别
                "_crawled": bool(full_content),  # 标记是否已爬取
                "_summary": summary  # 保存摘要信息
            })
            print(f"📌 {i}. {title}")
            print(f"   📎 {link}")
            if summary:
                print(f"   📝 {summary[:50]}...")

        # 计算内容哈希以检查重复
        content_hashes = [content_hash(news["content"]) for news in formatted_news_list]
        existing_hashes = check_content_hashes(content_hashes)
        
        # 过滤掉已存在的新闻
        news_to_process = []
        duplicate_count = 0
        
        for news, hash_value in zip(formatted_news_list, content_hashes):
            if hash_value not in existing_hashes:
                news_to_process.append(news)
            else:
                duplicate_count += 1
        
        if not news_to_process:
            print("所有头条新闻已存在，无需保存")
            result["duplicate_count"] = duplicate_count
            return result
        
        print(f"⏳ 处理 {len(news_to_process)} 条头条新闻...")
        
        # 获取"top"类别的最近新闻用于比较
        window_size = int(os.getenv("WINDOW_SIZE", 5))
        existing_news = get_recent_news_with_embeddings(EMBEDDING_MODEL, "top", limit=window_size)
        
        # 提取已有的嵌入向量
        existing_embeddings = []
        for news in existing_news:
            if news['embedding'] is not None:
                existing_embeddings.append((news['id'], news['embedding']))
        
        if existing_embeddings:
            print(f"📊 为头条新闻进行嵌入相似度检查，已加载 {len(existing_embeddings)} 条现有嵌入")
            
            # 为新新闻顺序计算嵌入
            unique_news = []
            sim_duplicates = 0
            
            for news in news_to_process:
                emb = create_embedding(news['content'], EMBEDDING_MODEL)
                if emb is None:
                    # 如果嵌入失败，还是保留这条新闻
                    unique_news.append(news)
                    continue
                    
                # 检查是否与现有新闻相似
                is_similar = False
                for news_id, old_emb in existing_embeddings:
                    if cosine_sim(emb, old_emb) >= SIM_THRESHOLD:
                        print(f"🔄 发现相似头条新闻 (ID: {news_id}): {news['title']}")
                        is_similar = True
                        sim_duplicates += 1
                        break
                
                if not is_similar:
                    unique_news.append(news)
            
            duplicate_count += sim_duplicates
            print(f"📊 嵌入相似度检查: 发现 {sim_duplicates} 条相似新闻")
        else:
            # 如果没有可比较的嵌入，则所有通过哈希检查的新闻都视为唯一
            unique_news = news_to_process
        
        # 保存新闻到数据库
        if unique_news:
            saved_results = save_news(unique_news)
            
            # 为新保存的新闻创建嵌入
            if saved_results:
                news_embeddings = []
                news_tags = []
                
                # 为每条新保存的新闻计算嵌入和标签
                for news_id, info in saved_results.items():
                    if info.get('is_new'):
                        # 计算并保存嵌入
                        emb = create_embedding(info['content'], EMBEDDING_MODEL)
                        if emb is not None:
                            news_embeddings.append({
                                'news_id': news_id,
                                'embedding_vector': emb,
                                'model_name': EMBEDDING_MODEL
                            })
                        
                        # 计算并保存标签
                        # 找到原始新闻数据以获取标题
                        news_item = next((news for news in unique_news if news['content'] == info['content']), None)
                        if news_item:
                            print(f"🏷️ 正在分析头条新闻 {news_id} 的内容以生成标签...")
                            tag_info = analyze_news_content(info['content'], news_item.get('title'))
                            
                            # 查找已经爬取的摘要
                            summary = news_item.get('_summary')
                            if summary:
                                tag_info['summary'] = summary
                            
                            tag_info['news_id'] = news_id
                            news_tags.append(tag_info)
                
                # 保存所有嵌入
                if news_embeddings:
                    print(f"🔄 正在保存 {len(news_embeddings)} 条头条新闻嵌入")
                    save_news_embeddings(news_embeddings)
                
                # 保存所有标签
                if news_tags:
                    print(f"🔖 正在为 {len(news_tags)} 条头条新闻保存标签和摘要")
                    save_news_tags(news_tags)
            
            result["new_count"] = len(unique_news)
            
        else:
            print("所有头条新闻经过嵌入相似度检查后均已存在，无需保存")
        
        result["duplicate_count"] = duplicate_count
        return result
    
    except Exception as e:
        print(f"❗ 头条请求失败：{e}")
        import traceback
        traceback.print_exc()
        result["success"] = False
        result["error"] = str(e)
        return result

def process_category(category_info):
    """处理单个新闻类别的包装函数"""
    cat_name, cat_type = category_info
    try:
        print(f"🔄 开始处理 {cat_name}")
        if cat_type == 'top':
            result = fetch_tops()
        else:
            result = fetch_and_process(cat_type)
        
        if result and result.get('success'):
            new_count = result.get('new_count', 0)
            dup_count = result.get('duplicate_count', 0)
            print(f"✅ {cat_name} 完成: 新增{new_count}条，已存在{dup_count}条")
        else:
            print(f"❌ {cat_name} 失败")
            
        return (cat_name, cat_type, result)
    except Exception as e:
        print(f"❌ {cat_name} 出错: {str(e)}")
        return (cat_name, cat_type, e)

def main():
    """主函数：并行执行所有新闻获取流程"""
    # 首先初始化数据库，确保所有表都存在
    print("初始化数据库...")
    initialize_database()
    
    # 定义可用的新闻类别
    CATEGORIES = {
        'hk_us': '港美股新闻',
        'watch': '国内A股新闻',
        'top': '财联社头条'
    }
    
    # 更整洁的开始信息
    print("\n" + "="*30)
    print("开始并行获取财经新闻")
    print("="*30)
    
    # 记录开始时间
    start_time = datetime.now()
    
    # 准备并行处理的参数
    category_tasks = [(name, cat_type) for cat_type, name in CATEGORIES.items()]
    
    # 使用ThreadPoolExecutor并行处理
    category_results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        # 提交所有任务
        future_to_category = {
            executor.submit(process_category, task): task 
            for task in category_tasks
        }
        
        # 收集结果
        for future in as_completed(future_to_category):
            try:
                cat_name, cat_type, result = future.result()
                category_results[cat_type] = (cat_name, result)
            except Exception as e:
                task = future_to_category[future]
                cat_name, cat_type = task
                category_results[cat_type] = (cat_name, e)
    
    # 处理结果
    total_new = 0
    total_duplicate = 0
    errors = []
    
    # 整洁地显示结果汇总
    print("\n" + "-"*30)
    print("获取结果:")
    
    for cat_type in CATEGORIES.keys():
        if cat_type in category_results:
            cat_name, result = category_results[cat_type]
            
            if isinstance(result, Exception):
                print(f"• {cat_name}: ❌ 错误 ({str(result)[:50]}...)")
                errors.append(f"{cat_type}: {result}")
                continue
                
            if result and result.get('success'):
                new_count = result.get('new_count', 0)
                dup_count = result.get('duplicate_count', 0)
                total_new += new_count
                total_duplicate += dup_count
                status = "✅" if new_count > 0 else "🔄"
                print(f"• {cat_name}: {status} 新增{new_count}条，已存在{dup_count}条")
            else:
                print(f"• {cat_name}: ❌ 失败")
                if result:
                    errors.append(f"{cat_type}: {result.get('error', '未知错误')}")
        else:
            print(f"• {CATEGORIES[cat_type]}: ❌ 未处理")
    
    # 输出总体结果，更简洁明了
    print("\n" + "="*30)
    print(f"✅ 并行任务完成 (耗时: {(datetime.now() - start_time).total_seconds():.1f}秒)")
    print(f"📊 总计: 新增{total_new}条，已存在{total_duplicate}条")
    if errors:
        print(f"❌ 错误: {len(errors)}个")
    print("="*30)
    
    return 0 if not errors else 1

if __name__ == "__main__":
    """脚本入口点"""
    import sys
    sys.exit(main())