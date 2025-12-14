from flask import Blueprint, jsonify, request, current_app as app
from flask_jwt_extended import jwt_required, get_jwt_identity
import akshare as ak
from db.models import db, UserStock, Stocks, HotStock, StockRealtimeQuote, StockHistory, StockInfo, StockPinyin, StockForecast
from utils.ai_utils import extract_stocks_from_base64
from datetime import datetime, timedelta
from utils.redis_cache import redis_cache, get_cached_data, cache_data

# 创建蓝图
stock_bp = Blueprint('stock', __name__, url_prefix='/api')

############################################################
@stock_bp.route('/stocks/get', methods=['GET'])
@jwt_required()
def get_stocks():
    """获取当前用户的所有自选股票"""
    try:
        user_id = get_jwt_identity()
        app.logger.debug(f"[/stocks/get] 获取用户 {user_id} 的自选股")
        
        # 从UserStock获取用户关注的股票代码
        user_stocks = UserStock.query.filter_by(user_id=user_id).all()
        stock_codes = [stock.code for stock in user_stocks]
        
        if not stock_codes:
            app.logger.debug(f"[/stocks/get] 用户 {user_id} 没有自选股")
            return jsonify({
                'code': 0,
                'data': []
            })

        # 多表联查获取更多信息
        stock_info_query = db.session.query(
            Stocks.code,
            Stocks.name,
            Stocks.market,
            StockInfo.industry,
            StockRealtimeQuote.latest_price,
            StockRealtimeQuote.change_percent,
            UserStock.added_at
        ).join(
            UserStock, Stocks.code == UserStock.code
        ).outerjoin(
            StockInfo, Stocks.code == StockInfo.code
        ).outerjoin(
            StockRealtimeQuote, Stocks.code == StockRealtimeQuote.code
        ).filter(
            UserStock.user_id == user_id
        ).all()
        
        # 构建返回数据
        serialized_stocks = []
        for stock in stock_info_query:
            serialized_stocks.append({
                'id': user_id,
                'user_id': user_id,
                'code': stock.code,
                'name': stock.name,
                'market': stock.market,  # 添加市场信息
                'industry': stock.industry,  # 添加行业信息
                'latest_price': stock.latest_price,  # 添加最新价格
                'change_percent': stock.change_percent,  # 添加涨跌幅
                'added_at': stock.added_at.strftime('%Y-%m-%d %H:%M:%S') if stock.added_at else None,
            })
        app.logger.debug(f"[/stocks/get] 成功获取 {len(serialized_stocks)} 自选股")

        return jsonify({
            'code': 0,
            'data': serialized_stocks
        })
    except Exception as e:
        app.logger.error(f"[/stocks/get] 获取股票失败: {str(e)}")
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500


############################################################
# 添加股票
@stock_bp.route('/stocks/add', methods=['POST'])
@jwt_required()
def add_stocks():
    """批量添加自选股票"""
    try:
        user_id = get_jwt_identity()
        data = request.json

        if not data or 'stocks' not in data or not isinstance(data['stocks'], list):
            return jsonify({'code': 400, 'msg': '请求格式错误，需要提供stocks列表'}), 400

        if len(data['stocks']) > 20:
            return jsonify({'code': 400, 'msg': '单次最多添加20只股票'}), 400

        # 当前用户已有的股票代码集合
        existing_codes = {s.code for s in UserStock.query.filter_by(user_id=user_id).all()}

        added_stocks = []
        error_stocks = []

        for stock in data['stocks']:
            # 处理股票代码，去掉市场前缀（如SH、SZ）
            stock_code = stock['code'][-6:]

            # 检查股票是否已存在于stocks表
            stock_record = Stocks.query.filter_by(code=stock_code).first()
            if not stock_record:
                error_stocks.append({
                    'code': stock['code'],
                    'reason': '股票代码不存在'
                })
                continue

            # 跳过已添加的股票
            if stock_code in existing_codes:
                error_stocks.append({
                    'code': stock['code'],
                    'reason': '已在自选列表中'
                })
                continue

            # 验证股票代码有效性并获取名称
            try:
                stock_name = stock.get('name', '') or stock_record.name  # 优先使用传入的名称或数据库中的名称

                # 添加自选股
                new_stock = UserStock(
                    user_id=user_id,
                    code=stock_code,
                    added_at=datetime.now()  # 添加时间参数
                )
                db.session.add(new_stock)
                added_stocks.append({
                    'code': stock_code,
                    'name': stock_name
                })
                existing_codes.add(stock_code)  # 更新集合，防止本次请求中重复添加
                
            except Exception as e:
                app.logger.error(f"添加股票 {stock['code']} 时发生错误: {str(e)}")
                app.logger.exception(e)  # 记录完整堆栈
                error_stocks.append({
                    'code': stock['code'],
                    'reason': f'处理异常: {str(e)}'
                })

        db.session.commit()
        app.logger.info(f"[/stocks/add] 成功添加 {len(added_stocks)} 只股票，失败 {len(error_stocks)} 只")

        return jsonify({
            'code': 0,
            'data': {
                'added': added_stocks,
                'errors': error_stocks,
                'total_added': len(added_stocks)
            }
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"批量添加股票失败: {str(e)}")
        app.logger.exception(e)
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500


############################################################
@stock_bp.route('/stocks/remove', methods=['POST'])
@jwt_required()
def remove_stocks():
    """批量删除自选股票"""
    try:
        user_id = get_jwt_identity()
        app.logger.debug(f"[/stocks/remove] 用户 {user_id} 请求批量删除自选股票")
        data = request.json

        if not data or 'codes' not in data or not isinstance(data['codes'], list):
            app.logger.debug(f"[/stocks/remove] 请求数据格式错误: {data}")
            return jsonify({'code': 400, 'msg': '请求格式错误，需要提供codes列表'}), 400

        if len(data['codes']) > 50:
            app.logger.debug(f"[/stocks/remove] 请求删除的股票数量超过限制: {len(data['codes'])}")
            return jsonify({'code': 400, 'msg': '单次最多删除50只股票'}), 400

        # 修改: 使用正确的字段名 code 替换 stock_code
        to_delete = UserStock.query.filter(
            UserStock.code.in_(data['codes']),
            UserStock.user_id == user_id
        ).all()

        app.logger.debug(f"[/stocks/remove] 找到 {len(to_delete)} 条记录需要删除")

        # 记录成功删除的股票代码
        deleted_codes = []

        for stock in to_delete:
            # 修改: 使用正确的字段名 code 替换 stock_code
            deleted_codes.append(stock.code)
            db.session.delete(stock)

        db.session.commit()

        app.logger.debug(f"[/stocks/remove] 成功删除 {len(deleted_codes)} 条记录")

        # 返回已删除的股票代码和数量
        return jsonify({
            'code': 0,
            'data': {
                'deleted_codes': deleted_codes,
                'total_deleted': len(deleted_codes)
            }
        })
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"[/stocks/remove] 批量删除股票失败: {str(e)}")
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500


############################################################
# 图片添加股票接口
@stock_bp.route('/stocks/add_from_image', methods=['POST'])
@jwt_required()
def add_stocks_from_image():
    """通过图片OCR批量添加自选股票"""
    try:
        user_id = get_jwt_identity()
        app.logger.debug(f"处理用户 {user_id} 的图片识别请求")

        data = request.json
        if not data:
            app.logger.error("请求体为空或不是JSON格式")
            return jsonify({'code': 400, 'msg': '请求格式错误，需要JSON数据'}), 400

        if 'image' not in data or not data.get('image'):
            app.logger.error("请求中缺少image字段或为空")
            return jsonify({'code': 400, 'msg': '缺少必要的图片数据'}), 400

        # 获取base64图片数据
        image_base64 = data.get('image')
        app.logger.info(f"接收到图片数据，长度: {len(image_base64)}, 前20字符: {image_base64[:20]}...")

        # 检查base64格式
        if "base64," in image_base64:
            prefix = image_base64.split("base64,")[0]

        try:
            # 使用AI工具提取股票信息
            app.logger.debug("开始调用OCR服务提取股票信息...")
            stock_items = extract_stocks_from_base64(image_base64)

            if not stock_items:
                app.logger.warning("OCR服务未能识别出任何股票信息")
                return jsonify({'code': 400, 'msg': '未从图片中识别出任何股票信息'}), 400

            app.logger.info(f"从图片中识别出 {len(stock_items)} 只股票: {stock_items}")

            # 解析识别结果，格式为："股票名称 股票代码"
            stocks_to_add = []
            rejected_items = []

            app.logger.debug("开始解析股票信息...")
            for i, item in enumerate(stock_items):
                parts = item.strip().split()

                if len(parts) >= 2:  # 确保至少有名称和代码两部分
                    code = parts[-1]
                    name = ' '.join(parts[:-1])

                    # 去除代码中的字母
                    code = ''.join(filter(str.isdigit, code))

                    # 验证代码格式（6位数字）
                    if code.isdigit() and len(code) == 6:
                        stocks_to_add.append({
                            'code': code,
                            'name': name
                        })
                        app.logger.debug(f"有效股票: {name} {code}")
                    else:
                        app.logger.warning(f"无效股票代码格式: {code}")
                        rejected_items.append({
                            'item': item,
                            'reason': '无效股票代码格式'
                        })
                else:
                    app.logger.warning(f"项目格式不正确: {item}")
                    rejected_items.append({
                        'item': item,
                        'reason': '格式不符合"名称 代码"'
                    })

            if not stocks_to_add:
                app.logger.warning(f"未能解析出有效股票信息，被拒绝的项: {rejected_items}")
                return jsonify({
                    'code': 400,
                    'msg': '未能正确解析出股票信息，请确保图片清晰',
                    'detail': rejected_items
                }), 400

            # 构造批量添加请求，调用已有的add_stocks逻辑
            add_request = {'stocks': stocks_to_add}
            app.logger.info(f"准备添加 {len(stocks_to_add)} 只股票: {stocks_to_add}")

            # 将股票添加请求暂存到session中
            session_key = f"pending_stocks_{user_id}"
            app.config[session_key] = add_request
            app.logger.debug(f"已将股票数据存入会话: {session_key}")

            # 返回预览信息，让用户确认
            return jsonify({
                'code': 0,
                'msg': f'成功识别出{len(stocks_to_add)}只股票',
                'data': {
                    'stocks': stocks_to_add,
                    'total': len(stocks_to_add),
                    'rejected': rejected_items if rejected_items else None
                }
            })

        except Exception as ocr_error:
            app.logger.error(f"图片识别处理失败: {str(ocr_error)}")
            app.logger.exception(ocr_error)  # 记录完整异常堆栈
            return jsonify({'code': 500, 'msg': f'图片处理失败: {str(ocr_error)}'}), 500

    except Exception as e:
        app.logger.error(f"添加股票图片处理失败: {str(e)}")
        app.logger.exception(e)  # 记录完整异常堆栈
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500


############################################################
@stock_bp.route('/stocks/confirm_from_image', methods=['POST'])
@jwt_required()
def confirm_stocks_from_image():
    """确认添加从图片中识别的股票"""
    try:
        user_id = get_jwt_identity()
        app.logger.debug(f"用户 {user_id} 确认添加图片识别的股票")

        # 从session获取暂存的股票数据
        session_key = f"pending_stocks_{user_id}"
        app.logger.debug(f"查找会话键: {session_key}")

        if session_key not in app.config:
            app.logger.warning(f"未找到会话数据: {session_key}")
            return jsonify({'code': 400, 'msg': '没有待确认的股票数据，请重新上传图片'}), 400

        # 获取暂存的股票列表并清除session
        add_request = app.config.pop(session_key)
        app.logger.info(f"从会话中取出待添加股票: {add_request}")

        # 使用已有的批量添加接口处理
        app.logger.debug("修改请求体，准备调用添加股票接口")
        request._cached_json = (add_request, request._cached_json[1])  # 修改请求的JSON数据
        app.logger.debug("调用 add_stocks() 完成添加")
        return add_stocks()

    except Exception as e:
        app.logger.error(f"确认添加图片股票失败: {str(e)}")
        app.logger.exception(e)  # 记录完整异常堆栈
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500



############################################################
@stock_bp.route('/stocks/search', methods=['GET'])
# @redis_cache("stock:search", expire_seconds=3600)  # 缓存1小时
def search_stocks():
    """搜索股票，支持代码、名称和拼音首字母搜索"""
    try:
        keyword = request.args.get('keyword', '').strip()
        limit = min(int(request.args.get('limit', 10)), 50)  # 默认10条，最多50条
        market = request.args.get('market', '').strip().upper()  # 新增市场参数

        if not keyword or len(keyword) < 1:
            return jsonify({
                'code': 400,
                'msg': '搜索关键词不能为空'
            }), 400

        # 默认搜索市场
        default_markets = ['SZ', 'SH', 'BJ']
        search_markets = []
        
        if market:
            # 如果指定了市场，验证市场代码是否有效
            valid_markets = ['SZ', 'SH', 'BJ']  # 只支持这三个市场
            if market in valid_markets:
                search_markets = [market]
            else:
                return jsonify({
                    'code': 400,
                    'msg': f'无效的市场代码: {market}，支持的市场代码: {", ".join(valid_markets)}'
                }), 400
        else:
            # 使用默认市场
            search_markets = default_markets

        app.logger.debug(f"[/stocks/search] 搜索股票，关键词: {keyword}, 市场: {search_markets}, 限制: {limit}")

        # 创建查询，添加市场过滤条件
        base_query = db.session.query(Stocks.code, Stocks.name, Stocks.market).filter(
            Stocks.market.in_(search_markets)
        ).distinct()

        # 根据代码或名称查询
        code_name_results = base_query.filter(
            (Stocks.code.like(f"%{keyword}%")) | 
            (Stocks.name.like(f"%{keyword}%"))
        )

        # 根据拼音首字母查询
        pinyin_results = base_query.join(StockPinyin, Stocks.code == StockPinyin.code).filter(
            StockPinyin.pinyin.like(f"%{keyword}%")
        )

        # 合并结果并去重
        combined_query = code_name_results.union(pinyin_results).limit(limit)
        stocks = combined_query.all()

        # 构建返回数据，包含市场信息
        results = [{'code': stock.code, 'name': stock.name, 'market': stock.market} for stock in stocks]

        app.logger.debug(f"[/stocks/search] 搜索结果数量: {len(results)}")

        return jsonify({
            'code': 0,
            'data': {
                'stocks': results,
                'total': len(results),
                'keyword': keyword,
            }
        })
    except Exception as e:
        app.logger.error(f"[/stocks/search] 搜索接口异常: {str(e)}")
        return jsonify({
            'code': 500,
            'msg': f'服务器内部错误: {str(e)}'
        }), 500


############################################################
@stock_bp.route('/stocks/hot', methods=['GET'])
@redis_cache("stock:hot", expire_seconds=600)  # 缓存10分钟
def get_hot_stocks():
    """
    获取热门股票排行榜
    """
    try:
        # 获取查询参数，默认为 "国内人气榜"
        symbol = request.args.get('symbol', '国内人气榜')
        if symbol not in {"国内人气榜", "港股人气榜"}:
            return jsonify({'code': 400, 'msg': '参数错误，symbol必须为"国内人气榜"或"港股人气榜"'}), 400

        app.logger.debug(f"[/stocks/hot] 获取热门股票排行榜，symbol: {symbol}")

        # 从HotStock表获取热门股票数据
        hot_stocks_query = db.session.query(
            HotStock.code,
            HotStock.rank,
            Stocks.name,
            Stocks.market,  # 添加市场字段
            StockInfo.industry,  # 添加行业字段
            StockRealtimeQuote.latest_price,
            StockRealtimeQuote.change_percent
        ).join(
            Stocks, HotStock.code == Stocks.code
        ).join(
            StockRealtimeQuote, HotStock.code == StockRealtimeQuote.code
        ).outerjoin(  # 使用外连接，防止没有行业信息的股票被过滤
            StockInfo, HotStock.code == StockInfo.code
        ).filter(
            HotStock.remark == symbol
        ).order_by(
            HotStock.rank.asc()
        ).limit(20)

        hot_stocks = [
            {
                'code': stock.code,
                'name': stock.name,
                'market': stock.market,  # 添加市场字段到返回数据
                'industry': stock.industry,  # 添加行业字段到返回数据
                'rank': stock.rank,
                'latest_price': stock.latest_price,
                'change_percent': stock.change_percent
            }
            for stock in hot_stocks_query
        ]

        app.logger.debug(f"[/stocks/hot] 成功获取 {len(hot_stocks)} 条热门股票数据")

        return jsonify({
            'code': 0,
            'msg': '获取热门股票成功',
            'data': hot_stocks
        })
    except Exception as e:
        app.logger.error(f"[/stocks/hot] 获取热门股票失败: {str(e)}")
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500


############################################################
@stock_bp.route('/stocks/history', methods=['GET'])
def get_stock_history():
    """获取股票历史价格走势"""
    try:
        # 获取请求参数
        raw_code = request.args.get('code')
        if not raw_code:
            return jsonify({'code': 400, 'msg': '请提供股票代码(code)'}), 400

        clean_code = raw_code[-6:]
        
        # 生成缓存键，包含股票代码
        cache_key = f"stock:history:{clean_code}"
        
        # 先尝试从缓存获取
        cached_result = get_cached_data(cache_key)
        if cached_result is not None:
            app.logger.debug(f"[stocks/history] 缓存命中: {cache_key}")
            return cached_result
            
        # 获取时间范围参数，默认为近3年
        years = 3
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=years * 365)).strftime('%Y%m%d')
        
        app.logger.info(f"获取股票 {raw_code} (处理为 {clean_code}) 的历史价格走势，时间范围: {start_date} ~ {end_date}")
        
        # 优先从数据库中查询历史数据
        history_records = StockHistory.query.filter(
            StockHistory.code == clean_code,
            StockHistory.date >= datetime.strptime(start_date, '%Y%m%d').date(),
            StockHistory.date <= datetime.strptime(end_date, '%Y%m%d').date()
        ).order_by(StockHistory.date.asc()).all()

        if history_records:
            app.logger.info(f"从数据库中获取到股票 {clean_code} 的历史记录，共 {len(history_records)} 条")
            history_data = [
                {
                    'date': record.date.strftime('%Y-%m-%d'),
                    'open_price': record.open_price,
                    'close_price': record.close_price,
                    'high': record.high,
                    'low': record.low,
                    'volume': record.volume,
                    'turnover': record.turnover,
                    'amplitude': record.amplitude,
                    'change_percent': record.change_percent,
                    'change_amount': record.change_amount,
                    'turnover_rate': record.turnover_rate
                }
                for record in history_records
            ]
        else:
            app.logger.info(f"数据库中未找到股票 {clean_code} 的历史记录，调用 akshare 接口获取数据")
            # 调用 akshare 接口获取历史数据
            stock_history_df = ak.stock_zh_a_hist(
                symbol=clean_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="hfq"
            )

            if stock_history_df is None or stock_history_df.empty:
                app.logger.warning(f"未获取到股票 {clean_code} 的历史价格数据")
                return jsonify({'code': 404, 'msg': f'未找到股票 {raw_code} 的历史价格数据'}), 404

            # 格式化数据并重命名字段
            stock_history_df.rename(columns={
                '日期': 'date',
                '开盘': 'open_price',
                '收盘': 'close_price',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'turnover',
                '振幅': 'amplitude',
                '涨跌幅': 'change_percent',
                '涨跌额': 'change_amount',
                '换手率': 'turnover_rate'
            }, inplace=True)
            stock_history_df['date'] = stock_history_df['date'].astype(str)

            # 移除多余字段（如 '股票代码'）
            history_data = stock_history_df.drop(columns=['股票代码'], errors='ignore').to_dict(orient='records')

            # 写入数据库
            for row in history_data:
                new_record = StockHistory(
                    code=clean_code,
                    date=datetime.strptime(row['date'], '%Y-%m-%d').date(),
                    open_price=row['open_price'],
                    close_price=row['close_price'],
                    high=row['high'],
                    low=row['low'],
                    volume=row['volume'],
                    turnover=row['turnover'],
                    amplitude=row['amplitude'],
                    change_percent=row['change_percent'],
                    change_amount=row['change_amount'],
                    turnover_rate=row['turnover_rate']
                )
                db.session.add(new_record)
            db.session.commit()
            app.logger.info(f"成功将股票 {clean_code} 的历史数据写入数据库，共 {len(history_data)} 条")

        # 构建返回结果
        result = jsonify({
            'code': 0,
            'msg': '获取历史价格数据成功',
            'data': {
                'code': raw_code,  # 返回原始代码，保持一致性
                'history': history_data
            }
        })
        
        # 缓存结果，设置12小时过期时间 (43200秒)
        try:
            cache_success = cache_data(cache_key, result.get_json(), expire_seconds=43200)
            if cache_success:
                app.logger.debug(f"[stocks/history] 结果已缓存: {cache_key}")
            else:
                app.logger.warning(f"[stocks/history] 结果缓存失败: {cache_key}")
        except Exception as e:
            app.logger.error(f"[stocks/history] 缓存操作异常: {e}")
        
        return result
            
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"获取股票历史价格异常: {str(e)}")
        app.logger.exception(e)
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500


############################################################
@stock_bp.route('/stocks/detail', methods=['GET'])
def get_stock_detail():
    """获取股票详细信息，包括行业、地区、交易数据等"""
    try:
        # 获取股票代码
        raw_code = request.args.get('code')
        if not raw_code:
            return jsonify({'code': 400, 'msg': '请提供股票代码(code)'}), 400

        # 处理股票代码格式
        clean_code = raw_code[-6:]  # 提取纯数字部分
        
        # 生成缓存键，包含股票代码
        cache_key = f"stock:detail:{clean_code}"
        
        # 先尝试从缓存获取
        cached_result = get_cached_data(cache_key)
        if cached_result is not None:
            app.logger.debug(f"[stocks/detail] 缓存命中: {cache_key}")
            return cached_result

        app.logger.info(f"获取股票 {clean_code} 的详细信息")

        # 从 StockInfo 表获取基本信息
        stock_info = StockInfo.query.filter_by(code=clean_code).first()
        if not stock_info:
            app.logger.warning(f"未找到股票 {clean_code} 的基本信息")
            return jsonify({'code': 404, 'msg': f'未找到股票 {clean_code} 的基本信息'}), 404

        # 从 StockRealtimeQuote 表获取实时交易数据
        stock_quote = StockRealtimeQuote.query.filter_by(code=clean_code).first()
        if not stock_quote:
            app.logger.warning(f"未找到股票 {clean_code} 的实时交易数据")
            return jsonify({'code': 404, 'msg': f'未找到股票 {clean_code} 的实时交易数据'}), 404
        
        # 从 Stocks 表获取股票名称和市场代码
        stock_record = Stocks.query.filter_by(code=clean_code).first()
        if not stock_record:
            app.logger.warning(f"未找到股票 {clean_code} 的基础记录")
            return jsonify({'code': 404, 'msg': f'未找到股票 {clean_code} 的基础记录'}), 404
        
        # 检查数据是否过期(超过4分钟)且当前在交易时间内(9:30-16:30)
        now = datetime.now()
        data_age = now - stock_quote.updated_at
        
        # 计算当前时间分钟表示以便比较
        current_hour = now.hour
        current_minute = now.minute
        current_time_minutes = current_hour * 60 + current_minute
        trading_start_minutes = 9 * 60 + 30  # 9:30 转换为分钟数
        trading_end_minutes = 16 * 60 + 30   # 16:30 转换为分钟数
        
        # 判断是否在交易时间内
        is_trading_hours = (trading_start_minutes <= current_time_minutes <= trading_end_minutes)
        
        # 只有在交易时间内且数据过期时才更新
        if data_age.total_seconds() > 240 and is_trading_hours:  # 4分钟 = 240秒，且在交易时间内
            app.logger.info(f"股票 {clean_code} 的实时数据已过期，当前在交易时间内，最后更新时间: {stock_quote.updated_at}，获取最新数据")
            
            # 获取股票记录
            stock_record = Stocks.query.filter_by(code=clean_code).first()
            
            # 只有当market字段有值时才尝试调用API
            if stock_record and stock_record.market:
                try:
                    # 直接使用数据库中的市场前缀并转为大写
                    market_prefix = stock_record.market.upper()
                    xq_symbol = f"{market_prefix}{clean_code}"
                    
                    # 调用雪球API获取最新数据
                    app.logger.debug(f"调用 akshare 接口获取股票 {xq_symbol} 的最新数据")
                    stock_data_df = ak.stock_individual_spot_xq(symbol=xq_symbol)
                    
                    if stock_data_df is not None and not stock_data_df.empty:
                        # 将DataFrame转换为字典，方便访问数据
                        stock_data = dict(zip(stock_data_df['item'], stock_data_df['value']))
                        
                        # 更新股票实时数据
                        stock_quote.latest_price = float(stock_data.get('现价', stock_quote.latest_price))
                        stock_quote.change_percent = float(stock_data.get('涨幅', stock_quote.change_percent))
                        stock_quote.change_amount = float(stock_data.get('涨跌', stock_quote.change_amount))
                        stock_quote.volume = float(stock_data.get('成交量', stock_quote.volume))
                        stock_quote.turnover = float(stock_data.get('成交额', stock_quote.turnover))
                        stock_quote.amplitude = float(stock_data.get('振幅', stock_quote.amplitude))
                        stock_quote.high = float(stock_data.get('最高', stock_quote.high))
                        stock_quote.low = float(stock_data.get('最低', stock_quote.low))
                        stock_quote.open_price = float(stock_data.get('今开', stock_quote.open_price))
                        stock_quote.previous_close = float(stock_data.get('昨收', stock_quote.previous_close))
                        stock_quote.turnover_rate = float(stock_data.get('周转率', stock_quote.turnover_rate))
                        stock_quote.pe_ratio_dynamic = float(stock_data.get('市盈率(动)', stock_quote.pe_ratio_dynamic))
                        stock_quote.pb_ratio = float(stock_data.get('市净率', stock_quote.pb_ratio))
                        stock_quote.total_market_value = float(stock_data.get('流通值', stock_quote.total_market_value))
                        stock_quote.change_ytd = float(stock_data.get('今年以来涨幅', stock_quote.change_ytd))
                        stock_quote.updated_at = now
                        
                        # 保存更新到数据库
                        db.session.commit()
                        app.logger.info(f"成功从雪球更新了股票 {clean_code} 的实时数据")
                    else:
                        app.logger.warning(f"从雪球获取股票 {xq_symbol} 实时数据失败，使用数据库中的数据")
                except Exception as api_e:
                    app.logger.error(f"调用雪球API失败: {str(api_e)}")
                    app.logger.exception(api_e)
                    # 出错时回滚，继续使用数据库中的数据
                    db.session.rollback()
            else:
                app.logger.warning(f"股票 {clean_code} 缺少市场信息，无法调用雪球API，使用数据库中的过期数据")

        # 构建返回数据
        detail = {
            'code': raw_code,  # 返回原始代码，保持一致性
            'name': stock_record.name,
            'market': stock_record.market.upper(),  # 添加市场代码
            'industry': stock_info.industry,
            'listing_date': stock_info.listing_date.strftime('%Y-%m-%d') if stock_info.listing_date else None,
            'total_shares': stock_info.total_shares,
            'circulating_shares': stock_info.circulating_shares,
            'trading': {
                'current_price': stock_quote.latest_price,
                'change_percent': stock_quote.change_percent,
                'open': stock_quote.open_price,
                'high': stock_quote.high,
                'low': stock_quote.low,
                'volume': stock_quote.volume,
                'turnover': stock_quote.turnover,
                'market_cap': stock_quote.total_market_value,
                'change_5min': stock_quote.change_5min,
                'last_updated': stock_quote.updated_at.strftime('%Y-%m-%d %H:%M:%S')  # 添加最后更新时间
            }
        }

        app.logger.info(f"成功获取股票 {clean_code} 的详细信息")
        
        # 构建返回结果
        result = jsonify({
            'code': 0,
            'msg': '获取股票详细信息成功',
            'data': detail
        })
        
        # 缓存结果，设置1小时过期时间 (3600秒)
        try:
            cache_success = cache_data(cache_key, result.get_json(), expire_seconds=3600)
            if cache_success:
                app.logger.debug(f"[stocks/detail] 结果已缓存: {cache_key}")
            else:
                app.logger.warning(f"[stocks/detail] 结果缓存失败: {cache_key}")
        except Exception as e:
            app.logger.error(f"[stocks/detail] 缓存操作异常: {e}")
        
        return result

    except Exception as e:
        app.logger.error(f"获取股票详情异常: {str(e)}")
        app.logger.exception(e)
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500


@stock_bp.route('/stocks/forecast', methods=['GET'])
# @jwt_required()
def get_stock_forecast():
    """获取股票业绩预测信息"""
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({'code': 400, 'msg': '缺少股票代码参数'}), 400

        # 查询业绩预测数据
        forecasts = StockForecast.query.filter_by(code=code).order_by(StockForecast.report_period.desc()).all()
        
        data = []
        for forecast in forecasts:
            data.append({
                'id': forecast.id,
                'code': forecast.code,
                'report_period': forecast.report_period,
                'announcement_date': forecast.announcement_date.strftime('%Y-%m-%d') if forecast.announcement_date else None,
                'forecast_type': forecast.forecast_type,
                'profit_forecast_median': float(forecast.profit_forecast_median) if forecast.profit_forecast_median is not None else None,
                'profit_growth_median': float(forecast.profit_growth_median) if forecast.profit_growth_median is not None else None,
                'last_year_profit': float(forecast.last_year_profit) if forecast.last_year_profit is not None else None,
                'forecast_summary': forecast.forecast_summary
            })

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': data
        })

    except Exception as e:
        app.logger.error(f"获取股票业绩预测异常: {str(e)}")
        return jsonify({'code': 500, 'msg': f'服务器内部错误: {str(e)}'}), 500
