# ai_utils.py
"""
AI工具模块
"""

from __future__ import annotations
import base64
import os
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime
import json
import re
import requests
import httpx
import asyncio
from requests.exceptions import RequestException, Timeout, ConnectionError
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

# --------------------------------------------------------------------------- #
# 搜索客户端
# --------------------------------------------------------------------------- #
@dataclass
class SearchClient:
    """搜索API客户端，用于替代原WebCrawler类"""
    base_url: str = "https://duckapi.102465.xyz"
    timeout: int = 180  # 增加超时时间到180秒
    
    @dataclass
    class SearchResult:
        title: str
        link: str
        snippet: str
        position: int
    
    async def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        执行搜索并返回结果
        
        Args:
            query: 搜索查询字符串
            max_results: 返回的最大结果数
            
        Returns:
            SearchResult对象列表
        """
        try:
            # 添加排除特定网站的条件
            query = f"{query} -site:zhihu.com -site:finance.sina.com.cn -site:qianzhan.com"
      
            logging.info(f"正在通过API搜索: {query} (超时: {self.timeout}秒)")

            params = {
                "query": query,
                "max_results": max_results
            }
            
            logging.debug(f"API请求参数: {params}")
            search_url = f"{self.base_url}/search"
            logging.debug(f"请求URL: {search_url}")
            
            start_time = time.time()
            logging.debug(f"开始API请求: {start_time}")
            
            async with httpx.AsyncClient() as client:
                logging.debug("已创建httpx客户端")
                try:
                    response = await client.get(
                        search_url, 
                        params=params, 
                        timeout=self.timeout
                    )
                    elapsed = time.time() - start_time
                    logging.debug(f"API请求完成 ({elapsed:.2f}秒), 状态码: {response.status_code}")
                    response.raise_for_status()
                except httpx.TimeoutException as e:
                    elapsed = time.time() - start_time
                    logging.error(f"搜索请求超时 ({elapsed:.2f}秒): {str(e)}")
                    return []
                except Exception as e:
                    elapsed = time.time() - start_time
                    logging.error(f"请求过程中发生异常 ({elapsed:.2f}秒): {str(e)}")
                    raise
                
                try:
                    data = response.json()
                    logging.debug(f"成功解析响应JSON，结果数量: {len(data.get('results', []))}")
                except Exception as e:
                    logging.error(f"解析JSON响应失败: {str(e)}")
                    logging.debug(f"响应内容: {response.text[:500]}...")
                    return []
                
                results = []
                for idx, result in enumerate(data.get("results", [])):
                    results.append(
                        self.SearchResult(
                            title=result.get("title", ""),
                            link=result.get("link", ""),
                            snippet=result.get("snippet", ""),
                            position=result.get("position", idx + 1)
                        )
                    )
                
                logging.info(f"成功找到 {len(results)} 条结果，请求耗时: {elapsed:.2f}秒")
                return results
                
        except httpx.TimeoutException as e:
            logging.error(f"搜索请求超时: {str(e)}")
            return []
        except httpx.HTTPError as e:
            logging.error(f"HTTP错误: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"搜索过程中发生意外错误: {str(e)}")
            import traceback
            logging.error(f"详细错误信息: {traceback.format_exc()}")
            return []
    
    async def fetch_content(self, url: str) -> str:
        """
        获取和解析网页内容
        
        Args:
            url: 要获取内容的网页URL
            
        Returns:
            解析后的网页文本内容
        """
        try:
            logging.info(f"正在通过API获取内容: {url} (超时: {self.timeout}秒)")
            
            params = {"url": url}
            
            start_time = time.time()
            logging.debug(f"开始获取内容请求: {start_time}")
            
            fetch_url = f"{self.base_url}/fetch"
            logging.debug(f"请求URL: {fetch_url}, 参数: {params}")
            
            async with httpx.AsyncClient() as client:
                logging.debug("已创建httpx客户端")
                try:
                    response = await client.get(
                        fetch_url, 
                        params=params, 
                        timeout=self.timeout
                    )
                    elapsed = time.time() - start_time
                    logging.debug(f"获取内容请求完成 ({elapsed:.2f}秒), 状态码: {response.status_code}")
                    response.raise_for_status()
                except httpx.TimeoutException as e:
                    elapsed = time.time() - start_time
                    logging.error(f"获取内容请求超时 ({elapsed:.2f}秒): {str(e)}")
                    return f"错误: 获取网页时请求超时 ({elapsed:.2f}秒)。"
                except Exception as e:
                    elapsed = time.time() - start_time
                    logging.error(f"获取内容请求过程中发生异常 ({elapsed:.2f}秒): {str(e)}")
                    raise
                
                try:
                    data = response.json()
                    content = data.get("content", "")
                    logging.debug(f"成功解析响应JSON，内容长度: {len(content)}")
                except Exception as e:
                    logging.error(f"解析JSON响应失败: {str(e)}")
                    logging.debug(f"响应内容: {response.text[:500]}...")
                    return f"错误: 解析响应失败: {str(e)}"
                
                logging.info(f"成功获取并解析内容 ({len(content)} 字符), 请求耗时: {elapsed:.2f}秒")
                return content
                
        except httpx.TimeoutException as e:
            logging.error(f"请求URL超时: {url}, 错误: {str(e)}")
            return f"错误: 获取网页时请求超时。"
        except httpx.HTTPError as e:
            logging.error(f"获取 {url} 时发生HTTP错误: {str(e)}")
            return f"错误: 无法访问网页 ({str(e)})"
        except Exception as e:
            logging.error(f"从 {url} 获取内容时出错: {str(e)}")
            import traceback
            logging.error(f"详细错误信息: {traceback.format_exc()}")
            return f"错误: 获取网页时发生意外错误 ({str(e)})"
    
    def format_results(self, results: List[SearchResult]) -> str:
        """将搜索结果格式化为可读文本"""
        if not results:
            return "未找到搜索结果。可能是因为搜索API的机器人检测或没有匹配项。请尝试重新表述您的搜索或稍后再试。"

        output = []
        output.append(f"找到 {len(results)} 条搜索结果:\n")

        for result in results:
            output.append(f"{result.position}. {result.title}")
            output.append(f"   URL: {result.link}")
            output.append(f"   摘要: {result.snippet}")
            output.append("")  # 结果之间的空行

        return "\n".join(output)

# --------------------------------------------------------------------------- #
# LLM Client
# --------------------------------------------------------------------------- #
@dataclass
class LLMClient:
    base_url: str = os.getenv("LLM_BASE_URL")
    api_key: str = os.getenv("LLM_API_KEY")
    default_model: str = os.getenv("LLM_MODEL")
    timeout: int = 180  # 增加超时时间（秒）
    max_content_length: int = 409600  # 最大内容长度限制
    client: OpenAI | None = None

    def __post_init__(self):
        if not (self.base_url and self.api_key and self.default_model):
            raise RuntimeError(
                "请设置环境变量 LLM_BASE_URL, LLM_API_KEY, LLM_MODEL"
            )
        # 初始化 OpenAI 客户端实例
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url.rstrip("/"),
            timeout=self.timeout,  # 设置全局超时时间
        )

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_retries: int = 5,  # 增加重试次数
        retry_delay: int = 3,  # 重试延迟（秒）
    ) -> str:
        # 确保消息内容不超过最大长度
        processed_messages: List[Dict[str, str]] = []
        for msg in messages:
            content = msg.get("content", "")
            if len(content) > self.max_content_length:
                content = (
                    content[: self.max_content_length]
                    + f"\n...(内容已截断，原长度:{len(content)}字符)"
                )
            processed_messages.append({
                "role": msg.get("role", "user"),
                "content": content,
            })

        retries = 0
        last_error = None
        while retries < max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=model or self.default_model,
                    messages=processed_messages,
                    temperature=temperature,
                )
                return response.choices[0].message.content.strip()
            except (RequestException, ConnectionError, Timeout) as e:
                retries += 1
                last_error = e
                logging.warning(f"[LLMClient] 请求失败，重试 {retries}/{max_retries}: {e}")
                if retries < max_retries:
                    time.sleep(retry_delay * retries)  # 指数退避重试延迟
                else:
                    logging.error(f"[LLMClient] 请求彻底失败，已重试 {max_retries} 次: {e}")
            except Exception as e:
                # 捕获其他所有异常
                logging.error(f"[LLMClient] 未预期的错误: {e}", exc_info=True)
                retries += 1
                if retries < max_retries:
                    time.sleep(retry_delay)
                else:
                    break
        
        # 重试失败后返回回退消息
        error_msg = f"请求失败，已重试 {max_retries} 次: {last_error or '未知错误'}"
        logging.error(f"[LLMClient] {error_msg}")
        raise RuntimeError(error_msg)

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
    ):
        """
        流式对话接口
        """
        # 确保消息内容不超过最大长度
        processed_messages: List[Dict[str, str]] = []
        for msg in messages:
            content = msg.get("content", "")
            if len(content) > self.max_content_length:
                content = (
                    content[: self.max_content_length]
                    + f"\n...(内容已截断，原长度:{len(content)}字符)"
                )
            processed_messages.append({
                "role": msg.get("role", "user"),
                "content": content,
            })

        try:
            stream = self.client.chat.completions.create(
                model=model or self.default_model,
                messages=processed_messages,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logging.error(f"[LLMClient] 流式请求失败: {e}", exc_info=True)
            yield f"Error: {str(e)}"

    def analyze_financial_news(self, news_text: str) -> Dict[str, Any]:
        """返回 {'conclusion': '利好|利空|中性', 'reason': '...', 'news_list': ['新闻标题1', '新闻标题2', ...]}"""
        if len(news_text) > self.max_content_length:
            news_text = (
                news_text[: self.max_content_length]
                + f"\n...(内容已截断，原长度:{len(news_text)}字符)"
            )

        prompt = (
            "你是一个金融分析师，请根据以下一系列新闻判断其对市场的影响，"
            "结论应为【重大利好】、【利好】、【利空】、【重大利空】或【中性】，并简要说明理由。\n\n"
            "请注意：如果在理由中引用了具体新闻，请使用 Markdown 超链接格式包装新闻，"
            "即使用 `[新闻标题](新闻链接)` 的形式，使其可以点击访问。\n\n"
            "需要给出参考的新闻列表，新闻列表不能重复，仅仅给出有意义、有参考价值、评价过程中使用到的新闻。\n\n"
            "新闻内容：\n"
            f"{news_text}\n\n"
            "请严格按照格式回答：\n"
            "结论：【重大利好/重大利空/利好/利空/中性】\n"
            "理由：XXX\n"
            "新闻列表："
            "1. [新闻标题1](链接1)\n"
            "2. [新闻标题2](链接2)\n"
            "3. [新闻标题3](链接3)\n"
            "...\n"
        )

        try:
            reply = self.chat(
                [{"role": "user", "content": prompt}],
                model=self.default_model,
                temperature=0.5,
                max_retries=5,
            )
            
            conclusion = "未知"
            for c in ("重大利好", "利好", "中性", "利空", "重大利空"):
                if f"【{c}】" in reply:
                    conclusion = c
                    break

            # 提取理由
            reason = reply.split("理由：", 1)[-1].split("新闻列表：", 1)[0].strip()

            # 提取新闻列表
            news_list_section = reply.split("新闻列表：", 1)[-1].strip()
            news_list = []
            for line in news_list_section.splitlines():
                line = line.strip()
                if line and line[0].isdigit() and line[1] == '.':  # 匹配以数字加点开头的条目
                    news_list.append(line)

            return {"conclusion": conclusion, "reason": reason, "news_list": news_list}
        except Exception as e:
            logging.error(f"分析金融新闻失败: {e}", exc_info=True)
            return {"conclusion": "未知", "reason": f"分析失败: {str(e)}", "news_list": []}

    async def search_stocks_by_tag(self, tag: str, crawler: SearchClient = None, max_pages: int = 10) -> Dict[str, Any]:
        """
        根据股票标签搜索相关股票信息
        
        Args:
            tag: 股票标签，如"苏超概念股"
            crawler: SearchClient实例，如果为None则使用全局实例
            max_pages: 最大爬取页面数量
            
        Returns:
            包含相关股票名称和原因的字典
        """
        # 如果没有传入crawler，则使用全局实例
        if crawler is None:
            crawler = web_crawler
            
        logging.info(f"开始搜索股票标签: {tag}")
        
        # 1. 使用API搜索相关内容
        search_query = f"{tag} 相关的A股"
        search_results = await crawler.search(search_query, max_results=max_pages)
        
        if not search_results:
            return {"status": "error", "message": f"未找到与'{tag}'相关的搜索结果"}
        
        # 2. 构建提示词，要求模型选择要爬取的页面
        search_results_formatted = crawler.format_results(search_results)
        
        extract_pages_prompt = f"""
        我需要查找与"{tag}"相关的中国A股市场股票信息。以下是搜索结果:
        
        {search_results_formatted}
        
        请分析这些搜索结果，并以JSON格式返回最有可能包含与"{tag}"相关的龙头个股列表的页面ID。
        返回格式如下:
        ```json
        {{
            "page_ids": [1, 2, 3],  // 页面位置ID列表，最多选择5个最相关的页面
            "reason": "为什么选择这些页面的简短说明"
        }}
        ```
        仅返回JSON数据，不要有其他解释。
        """
        
        # 3. 发送请求给模型，获取要爬取的页面ID
        try:
            page_ids_response = self.chat(
                messages=[{"role": "user", "content": extract_pages_prompt}],
                temperature=0.3
            )
            
            # 处理可能被```包裹的JSON
            page_ids_data = self._extract_json(page_ids_response)
            
            if not page_ids_data or 'page_ids' not in page_ids_data:
                return {"status": "error", "message": "模型未能正确返回页面ID"}
            
            page_ids = page_ids_data.get('page_ids', [])
            if not page_ids:
                return {"status": "error", "message": "未找到合适的页面ID"}
                
            # 4. 获取选定页面的内容
            pages_content = []
            for page_id in page_ids:
                if 1 <= page_id <= len(search_results):
                    page_url = search_results[page_id-1].link
                    logging.info(f"正在爬取页面 {page_id}: {page_url}")
                    content = await crawler.fetch_content(page_url)
                    pages_content.append({
                        "page_id": page_id,
                        "url": page_url,
                        "title": search_results[page_id-1].title,
                        "content": content[:20000]  # 限制内容长度
                    })
            
            if not pages_content:
                return {"status": "error", "message": "未能成功爬取任何页面内容"}
            
            # 5. 构建提取股票信息的提示词
            extract_stocks_prompt = f"""
            我需要从以下网页内容中提取与"{tag}"相关的股票信息。请分析这些内容，找出相关的股票名称以及它们与"{tag}"的关联原因。
            请你注意：name是A股股票的名称，如“上汽集团”，不要在股票名称中包含股票代码等多余的信息，只需要股票的完整名称
            网页内容:
            ```
            {json.dumps(pages_content, ensure_ascii=False)}
            ```

            请以JSON格式返回结果，格式如下:
            ```json
            {{
                "tag": "{tag}",
                "stocks": [
                    {{
                        "name": "股票名称",
                        "reason": "与{tag}相关的原因描述"
                    }},
                    // ...更多股票
                ]
            }}
            ```
            仅返回JSON数据，不要有其他解释。如果未找到相关股票，则返回空列表。
            """
            
            # 6. 发送请求提取股票信息
            stocks_response = self.chat(
                messages=[{"role": "user", "content": extract_stocks_prompt}],
            )
            
            # 处理可能被```包裹的JSON
            stocks_data = self._extract_json(stocks_response)
            
            if not stocks_data:
                return {"status": "error", "message": "模型未能正确返回股票信息"}
            
            # 7. 返回结果
            return {
                "status": "success", 
                "data": stocks_data,
                "raw_response": stocks_response
            }
            
        except Exception as e:
            logging.error(f"搜索股票信息过程中出错: {str(e)}", exc_info=True)
            return {"status": "error", "message": f"处理过程中出错: {str(e)}"}

    def _extract_json(self, text: str) -> Dict:
        """从文本中提取JSON数据，处理可能被```包裹的情况"""
        try:
            # 尝试直接解析
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取被```包裹的JSON
            json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
            matches = re.findall(json_pattern, text)
            
            if matches:
                try:
                    return json.loads(matches[0])
                except json.JSONDecodeError:
                    pass
            
            # 尝试从文本中查找{开始和}结束的部分
            try:
                start_idx = text.find('{')
                end_idx = text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = text[start_idx:end_idx]
                    return json.loads(json_str)
            except:
                pass
                
        logging.warning(f"无法从以下文本中提取JSON:\n{text}")
        return {}

# --------------------------------------------------------------------------- #
# OCR Client
# --------------------------------------------------------------------------- #
@dataclass
class OCRClient:
    timeout: int = 30
    ocr_api_url: str = "https://ocr.102465.xyz/ocr"
    
    @staticmethod
    def _image_to_base64(image_path: str) -> str:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def recognize(self, image_path: str) -> List[str]:
        """返回识别到的行文本 list[str]"""
        # 获取图片base64编码
        image_base64 = self._image_to_base64(image_path)
        return self.recognize_base64(image_base64)

    def recognize_base64(self, image_base64: str) -> List[str]:
        """从Base64图片识别文本，返回识别到的行文本 list[str]"""
        # 确保移除base64头部
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
            
        headers = {"Content-Type": "application/json"}
        data = {"image_base64": image_base64}
        
        # 添加异常处理和重试逻辑
        max_retries = 3
        for retry in range(max_retries):
            try:
                resp = requests.post(self.ocr_api_url, json=data, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                
                # 解析响应数据
                result = resp.json()
                if result.get("code") == 0:  # 成功
                    # 提取所有识别到的文本及其位置信息
                    text_items = []
                    for item in result.get("data", []):
                        if not item.get("text"):
                            continue
                        
                        # 每个item的box是[left, top, right, bottom]
                        text_items.append({
                            "text": item.get("text", ""),
                            "box": item.get("box", [0, 0, 0, 0]),
                            "top": item.get("box", [0, 0, 0, 0])[1],  # y坐标
                            "left": item.get("box", [0, 0, 0, 0])[0],  # x坐标
                        })
                    
                    # 没有识别到文本
                    if not text_items:
                        return []
                        
                    # 按y坐标（top）排序
                    text_items.sort(key=lambda x: x["top"])
                    
                    # 根据y坐标接近程度分组为行
                    threshold = 30  # 两行文本之间的最小垂直距离阈值
                    lines = []
                    current_line = [text_items[0]]
                    
                    for i in range(1, len(text_items)):
                        if abs(text_items[i]["top"] - current_line[0]["top"]) < threshold:
                            # 同一行
                            current_line.append(text_items[i])
                        else:
                            # 新的一行
                            # 按x坐标排序当前行的文本
                            current_line.sort(key=lambda x: x["left"])
                            # 拼接当前行文本并加入lines
                            lines.append(" ".join([item["text"] for item in current_line]))
                            # 开始新一行
                            current_line = [text_items[i]]
                    
                    # 处理最后一行
                    if current_line:
                        current_line.sort(key=lambda x: x["left"])
                        lines.append(" ".join([item["text"] for item in current_line]))
                    
                    logging.debug(f"[OCR] 识别成功: {lines}")

                    return lines
                else:
                    logging.error(f"[OCR] 识别失败: {result.get('message', '未知错误')}")
                    return []
                    
            except (RequestException, ConnectionError, Timeout) as e:
                logging.warning(f"[OCR] 请求失败，重试 {retry+1}/{max_retries}: {e}")
                if retry + 1 >= max_retries:
                    logging.error(f"[OCR] 请求彻底失败: {e}")
                    raise
                time.sleep(2)  # 重试前等待
        
        return []  # 如果所有重试都失败，返回空列表

# --------------------------------------------------------------------------- #
# 公共对外函数
# --------------------------------------------------------------------------- #
_llm = LLMClient()
_baidu_ocr = OCRClient()
_crawler = SearchClient()  # 使用新的SearchClient替代WebCrawler

def analyze_financial_news(text: str) -> Dict[str, Any]:
    """用 DeepSeek 判断新闻利好/利空/中性"""
    try:
        return _llm.analyze_financial_news(text)
    except Exception as e:
        logging.error(f"分析金融新闻失败: {e}", exc_info=True)
        return {"conclusion": "未知", "reason": f"分析失败: {str(e)}", "news_list": []}


def extract_stocks_from_image(image_path: str) -> List[str]:
    """从截图中提取 A 股股票名称 代码"""
    text_lines = _baidu_ocr.recognize(image_path)
    return _extract_stocks_from_text_lines(text_lines)


def extract_stocks_from_base64(image_base64: str) -> List[str]:
    """从Base64图片中提取A股股票（名称和代码）"""
    text_lines = _baidu_ocr.recognize_base64(image_base64)
    return _extract_stocks_from_text_lines(text_lines)


def _extract_stocks_from_text_lines(text_lines: List[str]) -> List[str]:
    prompt = (
        "以下是股票软件截图中的所有识别行，请你提取其中所有 A 股股票信息（股票名称和6位代码）：\n"
        "- 忽略不含股票的行；\n"
        "- 忽略\"涨幅、振幅、序号、最新价\"等非股票信息；\n"
        "- 返回格式：一行一个，格式为\"股票名称 股票代码\"；\n"
        "- 如果某行含多只股票，可拆分为多行返回；\n"
        "- 不要解释说明，直接返回结果。\n"
        "【开始】\n"
        f"{chr(10).join(text_lines)}\n"
        "【结束】"
    )
    try:
        reply = _llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_retries=3,
        )
        return [line.strip() for line in reply.splitlines() if line.strip()]
    except Exception as e:
        logging.error(f"提取股票信息失败: {e}", exc_info=True)
        return []

def get_tag_leaders(tag: str) -> Dict[str, Any]:
    """
    获取指定标签的龙头股票信息
    
    Args:
        tag: 股票标签，如"光伏"、"新能源"等
        
    Returns:
        Dict: 包含龙头股票的列表和相关信息
        格式：{"leaders": [{"name": "股票名称", "reason": "原因"}, ...], "tag": "标签名"}
    """
    import asyncio
    
    try:
        logging.info(f"开始查询标签 '{tag}' 的龙头股票")
        result = asyncio.run(search_stocks_by_tag(tag))
        
        if result.get("status") == "success" and "data" in result:
            data = result["data"]
            
            # 从返回数据中提取所需格式
            response = {
                "tag": data.get("tag", tag),
                "leaders": []
            }
            
            # 处理股票信息
            stocks = data.get("stocks", [])
            for stock in stocks:
                if "name" in stock and "reason" in stock:
                    response["leaders"].append({
                        "name": stock["name"],
                        "reason": stock["reason"]
                    })
            
            logging.info(f"标签 '{tag}' 查询成功，找到 {len(response['leaders'])} 只龙头股")
            return response
        else:
            logging.warning(f"标签 '{tag}' 查询失败: {result.get('message', '未知错误')}")
            return {"leaders": [], "tag": tag, "error": result.get("message", "查询失败")}
    except Exception as e:
        logging.error(f"获取标签 '{tag}' 龙头股票时出错: {e}", exc_info=True)
        return {"leaders": [], "tag": tag, "error": str(e)}

async def search_stocks_by_tag(tag: str, crawler: SearchClient = _crawler, max_pages: int = 10) -> Dict[str, Any]:
    """
    根据股票标签搜索相关股票信息
    
    Args:
        tag: 股票标签，如"苏超概念股"
        crawler: SearchClient实例，如果为None则使用全局实例
        max_pages: 最大爬取页面数量
        
    Returns:
        包含相关股票名称和原因的字典
    """
    return await _llm.search_stocks_by_tag(tag, crawler, max_pages)
