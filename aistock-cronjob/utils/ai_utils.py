# ai_utils.py
"""
AI工具模块
"""

from __future__ import annotations
import os
import logging
import time
from dataclasses import dataclass
from typing import List, Dict

from openai import OpenAI
from requests.exceptions import RequestException, Timeout, ConnectionError
import re
import json

# --------------------------------------------------------------------------- #
# DeepSeek Client (via OpenAI-compatible LLM)
# --------------------------------------------------------------------------- #
@dataclass
class DeepSeekClient:
    base_url: str = os.getenv("LLM_BASE_URL")
    api_key: str = os.getenv("LLM_API_KEY")
    default_model: str = os.getenv("LLM_MODEL")
    timeout: int = 180  # 增加超时时间（秒）
    max_content_length: int = 40960  # 最大内容长度限制
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
                logging.warning(f"[DeepSeekClient] 请求失败，重试 {retries}/{max_retries}: {e}")
                if retries < max_retries:
                    time.sleep(retry_delay * retries)  # 指数退避重试延迟
                else:
                    logging.error(f"[DeepSeekClient] 请求彻底失败，已重试 {max_retries} 次: {e}")
            except Exception as e:
                # 捕获其他所有异常
                logging.error(f"[DeepSeekClient] 未预期的错误: {e}", exc_info=True)
                retries += 1
                if retries < max_retries:
                    time.sleep(retry_delay)
                else:
                    break
        
        # 重试失败后返回回退消息
        error_msg = f"请求失败，已重试 {max_retries} 次: {last_error or '未知错误'}"
        logging.error(f"[DeepSeekClient] {error_msg}")
        raise RuntimeError(error_msg)

   
# --------------------------------------------------------------------------- #
# 公共对外函数
# --------------------------------------------------------------------------- #
_deepseek = DeepSeekClient(default_model="deepseek-ai/DeepSeek-V3")

def analyze_stocks_news(stocks_with_news):
    """
    分析股票相关新闻的重要性和影响
    
    参数:
    stocks_with_news: 包含股票及其新闻的列表，格式为：
    [
      {
        "stock_code": "代码",
        "stock_name": "名称",
        "industry": "行业",
        "news": [
          {
            "id": "新闻ID",
            "title": "标题",
            "publish_time": "发布时间",
            "content": "内容"
          },
          ...
        ]
      },
      ...
    ]
    stock_industry_info: 可选的股票行业信息列表
    
    返回:
    分析结果列表，包含每条新闻的评估
    """
    try:
        client = _deepseek

        prompt = f"""
下面是用户的自选股以及自选股对应最新的新闻，你作为一名金融资讯分析师将为用户提取出最重要、最迫切需要用户知道的新闻

{stocks_with_news}

请分析这些新闻对相关股票的影响。请注意以下几点：
1. 只需要返回对股票有明确重大利好或明确重大利空影响的新闻，
2. 新闻内容可能包含多条新闻，需逐条分析，
3. 分析结果需要严格以JSON数组格式返回，不应该包含任何多余内容，参考格式如下：
[
    {{
        "news_id": "6666",
        "evaluation": "重大利好",
        "reason": "xxx"
    }},
]

如果没有发现重大利好或重大利空的新闻，请直接返回空数组 []
"""
        messages = [
            {"role": "system", "content": "你是一位专业的金融分析师，擅长分析财经新闻对股票的影响。"},
            {"role": "user", "content": prompt}
        ]
        
        response = client.chat(messages)
        # 记录完整响应，便于调试
        logging.debug(f"AI原始响应: {response}")
        
        # 先尝试清理和标准化响应
        cleaned_response = response.strip()
        
        # 首先尝试直接解析整个响应
        try:
            result = json.loads(cleaned_response)
            return result
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```|(\[[\s\S]*?\]|\{[\s\S]*?\})'
            json_matches = re.findall(json_pattern, cleaned_response)
            
            for match in json_matches:
                # 取非空的匹配组
                json_str = match[0] if match[0] else match[1]
                json_str = json_str.strip()
                
                if json_str:
                    try:
                        result = json.loads(json_str)
                        return result
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON解析错误 (匹配部分): {e}, 内容: {json_str[:100]}...")
            
            # 特殊处理空数组的情况
            if '[]' in cleaned_response:
                return []
                
            logging.error(f"无法从AI响应中解析JSON，原始响应：{cleaned_response[:200]}...")
            return []
    except Exception as e:
        logging.error(f"分析股票新闻时发生错误: {str(e)}", exc_info=True)
        return []
