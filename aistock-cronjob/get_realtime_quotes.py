import os
import pandas as pd
import requests
import math
import logging
from typing import Dict, List
from datetime import datetime
from utils.save import save_realtime_quotes, initialize_database
from dotenv import load_dotenv

# 禁用不安全请求的警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv(override=True)

def get_tqdm():
    """获取 tqdm 进度条"""
    try:
        from tqdm import tqdm as inner_tqdm
    except ImportError:
        inner_tqdm = lambda x, **kwargs: x
    return inner_tqdm

def fetch_paginated_data(url: str, base_params: Dict, timeout: int = 15):
    """
    东方财富-分页获取数据并合并结果
    :param url: 请求URL
    :param base_params: 基础请求参数
    :param timeout: 请求超时时间
    :return: 合并后的数据
    """
    # 请求头，模拟浏览器行为
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive"
    }
    
    # 复制参数以避免修改原始参数
    params = base_params.copy()
    
    # 获取第一页数据，用于确定分页信息
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        first_page_data = r.json()
        logger.info("[成功] 成功获取第1页数据")
    except Exception as e:
        logger.error(f"获取第1页数据失败: {str(e)}", exc_info=True)
        return pd.DataFrame()
    
    # 计算分页信息
    per_page_num = len(first_page_data["data"]["diff"])
    total_page = math.ceil(first_page_data["data"]["total"] / per_page_num)
    
    # 存储所有页面数据
    temp_list = []
    
    # 添加第一页数据
    temp_list.append(pd.DataFrame(first_page_data["data"]["diff"]))
    
    # 获取进度条
    tqdm = get_tqdm()
    
    # 获取剩余页面数据
    for page in tqdm(range(2, total_page + 1), leave=False):
        params.update({"pn": page})
        
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            page_data = r.json()
            logger.info(f"成功获取第{page}页数据")
            
            inner_temp_df = pd.DataFrame(page_data["data"]["diff"])
            temp_list.append(inner_temp_df)
        except Exception as e:
            logger.warning(f"获取第{page}页失败，跳过此页: {str(e)}")
            continue
    
    # 合并所有数据
    if not temp_list:
        return pd.DataFrame()
        
    temp_df = pd.concat(temp_list, ignore_index=True)
    temp_df["f3"] = pd.to_numeric(temp_df["f3"], errors="coerce")
    temp_df.sort_values(by=["f3"], ascending=False, inplace=True, ignore_index=True)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"].astype(int) + 1
    return temp_df

def set_df_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """
    设置 pandas.DataFrame 为空的情况
    :param df: 需要设置命名的数据框
    :param cols: 字段的列表
    :return: 重新设置后的数据
    """
    if df.shape == (0, 0):
        return pd.DataFrame(data=[], columns=cols)
    else:
        df.columns = cols
        return df

def stock_zh_a_spot_em() -> pd.DataFrame:
    """
    东方财富网-沪深京 A 股-实时行情
    https://quote.eastmoney.com/center/gridlist.html#hs_a_board
    :return: 实时行情
    :rtype: pandas.DataFrame
    """
    url = "https://82.push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "100",
        "po": "1",
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
        "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,"
        "f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
    }
    temp_df = fetch_paginated_data(url, params)
    temp_df.columns = [
        "index",
        "_",
        "最新价",
        "涨跌幅",
        "涨跌额",
        "成交量",
        "成交额",
        "振幅",
        "换手率",
        "市盈率-动态",
        "量比",
        "5分钟涨跌",
        "代码",
        "_",
        "名称",
        "最高",
        "最低",
        "今开",
        "昨收",
        "总市值",
        "流通市值",
        "涨速",
        "市净率",
        "60日涨跌幅",
        "年初至今涨跌幅",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
    ]
    temp_df.rename(columns={"index": "序号"}, inplace=True)
    temp_df = temp_df[
        [
            "序号",
            "代码",
            "名称",
            "最新价",
            "涨跌幅",
            "涨跌额",
            "成交量",
            "成交额",
            "振幅",
            "最高",
            "最低",
            "今开",
            "昨收",
            "量比",
            "换手率",
            "市盈率-动态",
            "市净率",
            "总市值",
            "流通市值",
            "涨速",
            "5分钟涨跌",
            "60日涨跌幅",
            "年初至今涨跌幅",
        ]
    ]
    temp_df["最新价"] = pd.to_numeric(temp_df["最新价"], errors="coerce")
    temp_df["涨跌幅"] = pd.to_numeric(temp_df["涨跌幅"], errors="coerce")
    temp_df["涨跌额"] = pd.to_numeric(temp_df["涨跌额"], errors="coerce")
    temp_df["成交量"] = pd.to_numeric(temp_df["成交量"], errors="coerce")
    temp_df["成交额"] = pd.to_numeric(temp_df["成交额"], errors="coerce")
    temp_df["振幅"] = pd.to_numeric(temp_df["振幅"], errors="coerce")
    temp_df["最高"] = pd.to_numeric(temp_df["最高"], errors="coerce")
    temp_df["最低"] = pd.to_numeric(temp_df["最低"], errors="coerce")
    temp_df["今开"] = pd.to_numeric(temp_df["今开"], errors="coerce")
    temp_df["昨收"] = pd.to_numeric(temp_df["昨收"], errors="coerce")
    temp_df["量比"] = pd.to_numeric(temp_df["量比"], errors="coerce")
    temp_df["换手率"] = pd.to_numeric(temp_df["换手率"], errors="coerce")
    temp_df["市盈率-动态"] = pd.to_numeric(temp_df["市盈率-动态"], errors="coerce")
    temp_df["市净率"] = pd.to_numeric(temp_df["市净率"], errors="coerce")
    temp_df["总市值"] = pd.to_numeric(temp_df["总市值"], errors="coerce")
    temp_df["流通市值"] = pd.to_numeric(temp_df["流通市值"], errors="coerce")
    temp_df["涨速"] = pd.to_numeric(temp_df["涨速"], errors="coerce")
    temp_df["5分钟涨跌"] = pd.to_numeric(temp_df["5分钟涨跌"], errors="coerce")
    temp_df["60日涨跌幅"] = pd.to_numeric(temp_df["60日涨跌幅"], errors="coerce")
    temp_df["年初至今涨跌幅"] = pd.to_numeric(
        temp_df["年初至今涨跌幅"], errors="coerce"
    )
    return temp_df

# === 实时行情爬取 ===
def fetch_realtime_quotes() -> pd.DataFrame:
    """
    获取沪深京 A 股实时行情数据
    :return: 股票行情数据DataFrame
    """
    try:
        # 获取实时行情数据
        temp_df = stock_zh_a_spot_em()
        logger.info(f"获取到 {len(temp_df)} 条股票数据")
        
    except Exception as e:
        logger.error(f"实时行情获取失败，发生异常：{str(e)}", exc_info=True)
        return pd.DataFrame()
    
    # 检查是否获取到有效数据
    if temp_df.empty:
        logger.warning("未获取到股票数据，跳过后续处理")
        return pd.DataFrame()

    # 确保代码列为字符串类型
    temp_df["代码"] = temp_df["代码"].astype(str)

    # 转换为字典列表用于保存
    quotes_list = temp_df.to_dict(orient='records')

    # 保存数据
    save_realtime_quotes(quotes_list)
    logger.info("实时行情数据已成功保存到数据库")
    
    return temp_df

if __name__ == "__main__":
    # 添加东八区时间检测，只在交易时间内执行
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    
    # 转换为分钟表示的时间，方便比较
    current_time_in_minutes = current_hour * 60 + current_minute
    market_open_time = 9 * 60 + 0  # 9:30
    market_close_time = 17 * 60 + 30  # 16:30
    
    # 检查是否在交易时间内（9:30-16:30）
    if not (market_open_time <= current_time_in_minutes <= market_close_time):
        logger.info(f"当前时间 {now.strftime('%H:%M')} 不在交易时间（9:30-16:30）内，不进行数据爬取")
    else:
        logger.info(f"当前时间 {now.strftime('%H:%M')} 在交易时间内，开始爬取数据")
        initialize_database()
        fetch_realtime_quotes()
