#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import time
import logging
from sqlalchemy import text
from utils.db import get_db_session
from utils.db import SessionLocal as db  # 修复db未定义

import os
import time
from dataclasses import dataclass
from typing import List, Dict, Any
import json
import re
import httpx
from requests.exceptions import RequestException, Timeout, ConnectionError
from dotenv import load_dotenv
from openai import OpenAI
from utils.model import StockTagRelation, Stocks
from sqlalchemy import func

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
            logging.info(f"正在通过API搜索: {query} (超时: {self.timeout}秒)")
            query = f"{query} -site:zhihu.com -site:finance.sina.com.cn -site:qianzhan.com"
            params = {"query": query, "max_results": max_results}

            logging.debug(f"API请求参数: {params}")
            search_url = f"{self.base_url}/search"
            logging.debug(f"请求URL: {search_url}")

            start_time = time.time()
            logging.debug(f"开始API请求: {start_time}")

            async with httpx.AsyncClient() as client:
                logging.debug("已创建httpx客户端")
                try:
                    response = await client.get(
                        search_url, params=params, timeout=self.timeout
                    )
                    elapsed = time.time() - start_time
                    logging.debug(
                        f"API请求完成 ({elapsed:.2f}秒), 状态码: {response.status_code}"
                    )
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
                    logging.debug(
                        f"成功解析响应JSON，结果数量: {len(data.get('results', []))}"
                    )
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
                            position=result.get("position", idx + 1),
                        )
                    )

                logging.info(
                    f"成功找到 {len(results)} 条结果，请求耗时: {elapsed:.2f}秒"
                )
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
                        fetch_url, params=params, timeout=self.timeout
                    )
                    elapsed = time.time() - start_time
                    logging.debug(
                        f"获取内容请求完成 ({elapsed:.2f}秒), 状态码: {response.status_code}"
                    )
                    response.raise_for_status()
                except httpx.TimeoutException as e:
                    elapsed = time.time() - start_time
                    logging.error(f"获取内容请求超时 ({elapsed:.2f}秒): {str(e)}")
                    return f"错误: 获取网页时请求超时 ({elapsed:.2f}秒)。"
                except Exception as e:
                    elapsed = time.time() - start_time
                    logging.error(
                        f"获取内容请求过程中发生异常 ({elapsed:.2f}秒): {str(e)}"
                    )
                    raise

                try:
                    data = response.json()
                    content = data.get("content", "")
                    logging.debug(f"成功解析响应JSON，内容长度: {len(content)}")
                except Exception as e:
                    logging.error(f"解析JSON响应失败: {str(e)}")
                    logging.debug(f"响应内容: {response.text[:500]}...")
                    return f"错误: 解析响应失败: {str(e)}"

                logging.info(
                    f"成功获取并解析内容 ({len(content)} 字符), 请求耗时: {elapsed:.2f}秒"
                )
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
            raise RuntimeError("请设置环境变量 LLM_BASE_URL, LLM_API_KEY, LLM_MODEL")
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
            processed_messages.append(
                {
                    "role": msg.get("role", "user"),
                    "content": content,
                }
            )

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
                logging.warning(
                    f"[LLMClient] 请求失败，重试 {retries}/{max_retries}: {e}"
                )
                if retries < max_retries:
                    time.sleep(retry_delay * retries)  # 指数退避重试延迟
                else:
                    logging.error(
                        f"[LLMClient] 请求彻底失败，已重试 {max_retries} 次: {e}"
                    )
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

    async def search_stocks_by_tag(
        self, tag: str, crawler: SearchClient = None, max_pages: int = 10
    ) -> Dict[str, Any]:
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
                temperature=0.3,
            )

            # 处理可能被```包裹的JSON
            page_ids_data = self._extract_json(page_ids_response)

            if not page_ids_data or "page_ids" not in page_ids_data:
                return {"status": "error", "message": "模型未能正确返回页面ID"}

            page_ids = page_ids_data.get("page_ids", [])
            if not page_ids:
                return {"status": "error", "message": "未找到合适的页面ID"}

            # 4. 获取选定页面的内容
            pages_content = []
            for page_id in page_ids:
                if 1 <= page_id <= len(search_results):
                    page_url = search_results[page_id - 1].link
                    logging.info(f"正在爬取页面 {page_id}: {page_url}")
                    content = await crawler.fetch_content(page_url)
                    pages_content.append(
                        {
                            "page_id": page_id,
                            "url": page_url,
                            "title": search_results[page_id - 1].title,
                            "content": content[:10000],  # 限制内容长度
                        }
                    )

            if not pages_content:
                return {"status": "error", "message": "未能成功爬取任何页面内容"}

            # 5. 构建提取股票信息的提示词
            extract_stocks_prompt = f"""
            我需要从以下网页内容中提取与"{tag}"相关的股票信息。请分析这些内容，找出相关的股票名称以及它们与"{tag}"的关联原因。
            请你注意：name是A股股票的名称，如“上汽集团”，不要在股票名称中包含股票代码等多余的信息，只需要股票的完整名称
            最多返回80个A股股票的名称
            网页内容如下:
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
                "raw_response": stocks_response,
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
            json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
            matches = re.findall(json_pattern, text)

            if matches:
                try:
                    return json.loads(matches[0])
                except json.JSONDecodeError:
                    pass

            # 尝试从文本中查找{开始和}结束的部分
            try:
                start_idx = text.find("{")
                end_idx = text.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = text[start_idx:end_idx]
                    return json.loads(json_str)
            except:
                pass

        logging.warning(f"无法从以下文本中提取JSON:\n{text}")
        return {}


# --------------------------------------------------------------------------- #
# 公共对外函数
# --------------------------------------------------------------------------- #
_llm = LLMClient()
_crawler = SearchClient()  # 使用新的SearchClient替代WebCrawler


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
            response = {"tag": data.get("tag", tag), "leaders": []}

            # 处理股票信息
            stocks = data.get("stocks", [])
            for stock in stocks:
                if "name" in stock and "reason" in stock:
                    response["leaders"].append(
                        {"name": stock["name"], "reason": stock["reason"]}
                    )

            logging.info(
                f"标签 '{tag}' 查询成功，找到 {len(response['leaders'])} 只龙头股"
            )
            return response
        else:
            logging.warning(
                f"标签 '{tag}' 查询失败: {result.get('message', '未知错误')}"
            )
            return {
                "leaders": [],
                "tag": tag,
                "error": result.get("message", "查询失败"),
            }
    except Exception as e:
        logging.error(f"获取标签 '{tag}' 龙头股票时出错: {e}", exc_info=True)
        return {"leaders": [], "tag": tag, "error": str(e)}


async def search_stocks_by_tag(
    tag: str, crawler: SearchClient = _crawler, max_pages: int = 10
) -> Dict[str, Any]:
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


def get_latest_news_ids():
    """分别获取code=top、hk_us、cn的最新5条新闻id"""
    try:
        with get_db_session() as session:
            news_ids = []
            for code in ["top", "hk_us", "cn"]:
                query = text(
                    """
                    SELECT id FROM news
                    WHERE code = :code
                    ORDER BY ctime DESC
                    LIMIT 5
                """
                )
                result = session.execute(query, {"code": code})
                news_ids += [row.id for row in result]
            print(f"获取到最新新闻ID: {news_ids}")
            return news_ids
    except Exception as e:
        print(f"获取新闻ID失败: {e}")
        return []


def get_tag_ids_from_news(news_ids):
    """从news_tag_relations表中查询这些新闻id对应的tag_id"""
    if not news_ids:
        return []
    try:
        with get_db_session() as session:
            query = text(
                """
                SELECT DISTINCT tag_id FROM news_tag_relations
                WHERE news_id IN :news_ids
            """
            )
            result = session.execute(query, {"news_ids": tuple(news_ids)})
            tag_ids = [row.tag_id for row in result]
            print(f"新闻对应的tag_id: {tag_ids}")
            return tag_ids
    except Exception as e:
        print(f"获取tag_id失败: {e}")
        return []


def filter_tag_ids_not_in_stock(tag_ids):
    """去除已经在stock_tag_relations中存在的tag_id"""
    if not tag_ids:
        return []
    try:
        with get_db_session() as session:
            query = text(
                """
                SELECT DISTINCT tag_id FROM stock_tag_relations
                WHERE tag_id IN :tag_ids
            """
            )
            result = session.execute(query, {"tag_ids": tuple(tag_ids)})
            exist_tag_ids = set(row.tag_id for row in result)
            filtered = [tid for tid in tag_ids if tid not in exist_tag_ids]
            print(f"过滤后tag_id: {filtered}")
            return filtered
    except Exception as e:
        print(f"过滤tag_id失败: {e}")
        return []


def get_tag_names(tag_ids):
    """根据tag_id查询tag名字"""
    if not tag_ids:
        return []
    try:
        with get_db_session() as session:
            query = text(
                """
                SELECT id, name FROM tags
                WHERE id IN :tag_ids
            """
            )
            result = session.execute(query, {"tag_ids": tuple(tag_ids)})
            tags = [(row.id, row.name) for row in result]
            print(f"最终需要请求的标签: {tags}")
            return tags
    except Exception as e:
        print(f"获取标签名字失败: {e}")
        return []


def main():
    """主函数"""
    print("开始执行标签股票关联任务")
    # 1. 获取最新新闻id
    news_ids = get_latest_news_ids()
    if not news_ids:
        print("没有获取到新闻ID，退出程序")
        return
    # 2. 获取tag_id
    tag_ids = get_tag_ids_from_news(news_ids)
    if not tag_ids:
        print("没有获取到tag_id，退出程序")
        return
    # 3. 过滤已存在的tag_id
    tag_ids = filter_tag_ids_not_in_stock(tag_ids)
    if not tag_ids:
        print("没有需要处理的tag_id，退出程序")
        return
    # 4. 获取tag名字
    tags = get_tag_names(tag_ids)
    if not tags:
        print("没有需要处理的标签，退出程序")
        return

    # 5. 遍历标签并请求信息
    for tag_id, tag_name in tags:
        print(f"处理标签: {tag_name} (ID: {tag_id})")
        result = get_tag_leaders(tag_name)

        # 提取所有股票名称，用于查询股票代码
        stock_names = []
        for item in result.get("leaders", []):
            if "name" in item:
                stock_names.append(item["name"])

        print(f"需要查询的股票名称: {stock_names}")

        if not stock_names:
            continue

        # 使用数据库会话进行后续所有数据库操作
        from datetime import datetime
        try:
            with get_db_session() as session:
                # 使用股票名称查询数据库获取股票代码，增加market不为空的条件
                valid_stocks = (
                    session.query(
                        Stocks.code, Stocks.name, Stocks.market  # 保留market字段，用于后续处理
                    )
                    .filter(
                        Stocks.name.in_(stock_names),
                        func.length(Stocks.code) == 6,  # 确保股票代码是6位
                        Stocks.market != None,  # 添加market不为空的条件
                    )
                    .all()
                )

                print(f"数据库中找到 {len(valid_stocks)} 只有效股票")

                # 创建名称到信息的映射（使用名称作为键）
                stock_info_map = {stock.name: stock for stock in valid_stocks}

                # 更新结果并保存到数据库
                verified_leaders = []
                inserted_keys = set()  # 新增：本地去重
                for leader in result.get("leaders", []):
                    stock_name = leader.get("name", "")
                    if stock_name in stock_info_map:
                        stock = stock_info_map[stock_name]
                        code = stock.code
                        key = (code, tag_id)
                        if key in inserted_keys:
                            continue  # 本地已处理，跳过
                        inserted_keys.add(key)

                        # 将股票与标签的关系保存到数据库
                        try:
                            # 检查该关系是否已存在
                            relation = (
                                session.query(StockTagRelation)
                                .filter_by(code=code, tag_id=tag_id)
                                .first()
                            )

                            if not relation:
                                relation = StockTagRelation(
                                    code=code,
                                    tag_id=tag_id,
                                    created_at=datetime.now(),
                                    reason=leader.get("reason", ""),
                                )
                                session.add(relation)
                                print(f"添加标签 '{tag_name}' 与股票 {code} 的关联关系")

                            # 添加到已验证的龙头股票列表
                            verified_leaders.append(
                                {
                                    "code": code,
                                    "name": stock_name,
                                    "market": stock.market,  # 包含market信息
                                    "reason": leader.get("reason", ""),
                                }
                            )
                        except Exception as e:
                            print(f"保存股票与标签关联失败: {e}")
                            session.rollback()  # 回滚当前事务

                # 提交所有数据库变更
                try:
                    session.commit()
                    logging.info(
                        f"成功验证标签 '{tag_name}' 的龙头股票，最终数量: {len(verified_leaders)}，已保存到数据库"
                    )
                except Exception as e:
                    print(f"提交数据库变更失败: {e}")
                    session.rollback()  # 回滚整个批次
        except Exception as e:
            print(f"数据库操作失败: {e}")

    print("标签股票关联任务完成")


if __name__ == "__main__":
    main()
