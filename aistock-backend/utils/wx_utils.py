from flask import current_app as app
import requests
import time
import json
import redis
import os
import urllib.parse
from datetime import datetime

# 获取带缓存的微信 access_token
def get_wechat_access_token(force_refresh=True):
    """
    获取微信 access_token，优先从缓存获取，过期或强制刷新时重新获取并缓存
    
    Args:
        force_refresh: 是否强制刷新，即使缓存中有效
        
    Returns:
        access_token: 微信 access_token
    """
    try:
        # 获取 Redis 连接
        redis_url = app.config.get("REDIS_BROKER_URL") or os.getenv("REDIS_BROKER_URL")
        if not redis_url:
            app.logger.error("[WECHAT] Redis连接配置未找到，无法缓存access_token")
            return _request_new_access_token()  # 无法缓存时直接请求
            
        redis_conn = redis.Redis.from_url(redis_url)
        
        # 定义Redis中存储 access_token 的键名
        access_token_key = "wechat:access_token"
        
        # 如果不强制刷新，尝试从Redis获取缓存的token
        if not force_refresh:
            token_data = redis_conn.get(access_token_key)
            if token_data:
                token_info = json.loads(token_data)
                # 检查是否即将过期（留10分钟缓冲）
                now = time.time()
                if token_info['expires_at'] > now + 600:
                    app.logger.debug(f"[WECHAT] 使用缓存的access_token，还有{int(token_info['expires_at']-now)}秒过期")
                    return token_info['access_token']
                else:
                    app.logger.info("[WECHAT] access_token即将过期，准备刷新")
        
        # 如果缓存不存在、已过期或强制刷新，则重新获取
        access_token = _request_new_access_token()
        if access_token:
            # 保存到Redis，设置过期时间比官方少10分钟，确保安全更新
            expires_in = 7200  # 标准过期时间2小时
            expires_at = time.time() + expires_in
            
            token_info = {
                'access_token': access_token,
                'created_at': time.time(),
                'expires_at': expires_at
            }
            
            # 存储到Redis，设置过期时间为原始过期时间
            redis_conn.setex(
                access_token_key,
                time=expires_in,
                value=json.dumps(token_info)
            )
            
            app.logger.info(f"[WECHAT] 成功刷新access_token，将在{datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')}过期")
            return access_token
        else:
            app.logger.error("[WECHAT] 获取access_token失败")
            # 失败时尝试使用旧token（如果存在）
            old_token_data = redis_conn.get(access_token_key)
            if old_token_data:
                old_token_info = json.loads(old_token_data)
                app.logger.warning("[WECHAT] 使用可能已过期的access_token作为备用")
                return old_token_info['access_token']
            return None
            
    except Exception as e:
        app.logger.error(f"[WECHAT] 处理access_token时出错: {str(e)}")
        return _request_new_access_token()  # 错误时直接请求新token

def _request_new_access_token():
    """直接从微信服务器请求新的 access_token"""
    try:
        # 验证配置是否存在
        appid = app.config.get('WECHAT_SCAN_APPID')
        secret = app.config.get('WECHAT_SCAN_SECRET')
        
        if not appid:
            app.logger.critical("[WECHAT] 缺少WECHAT_SCAN_APPID配置")
            app.last_wx_error = "缺少AppID配置"
            return None
            
        if not secret:
            app.logger.critical("[WECHAT] 缺少WECHAT_SCAN_SECRET配置")
            app.last_wx_error = "缺少AppSecret配置"
            return None
            
        params = {
            'grant_type': 'client_credential',
            'appid': appid,
            'secret': secret
        }
        
        app.logger.debug(f"[WECHAT] 请求新的access_token，appid长度: {len(params['appid']) if params['appid'] else 0}")
        
        res = requests.get(
            'https://api.weixin.qq.com/cgi-bin/token',
            params=params,
            timeout=10
        )
        
        if res.status_code != 200:
            error_msg = f"HTTP错误: {res.status_code}"
            app.logger.error(f"[WECHAT] 获取access_token {error_msg}")
            app.last_wx_error = error_msg
            return None
            
        result = res.json()
        if 'access_token' in result:
            app.logger.info(f"[WECHAT] 成功获取新access_token: {result['access_token'][:10]}...")
            return result['access_token']
        else:
            error_code = result.get('errcode', 'unknown')
            error_msg = result.get('errmsg', 'unknown error')
            error_detail = f"code={error_code}, msg={error_msg}"
            app.logger.error(f"[WECHAT] 获取access_token失败: {error_detail}")
            
            # 记录详细错误信息，供上层调用方使用
            app.last_wx_error = error_detail
            
            if error_code == 40164:
                app.logger.critical("[WECHAT] IP白名单错误，请在微信公众平台添加当前服务器IP到白名单")
            elif error_code == 40001:
                app.logger.critical("[WECHAT] AppSecret错误，请检查配置")
            elif error_code == 41004:
                app.logger.critical("[WECHAT] AppSecret缺失，请检查配置")
                
            return None
            
    except Exception as e:
        app.logger.error(f"[WECHAT] 请求access_token异常: {str(e)}")
        app.last_wx_error = f"请求异常: {str(e)}"
        return None

# 请求获取ticket
def _request_new_jsapi_ticket():
    """直接从微信服务器请求新的 jsapi_ticket"""
    try:
        access_token = get_wechat_access_token()
        if not access_token:
            app.logger.error("[WECHAT] 无法获取access_token，无法获取jsapi_ticket")
            return None
            
        params = {
            'access_token': access_token,
            'type': 'jsapi'
        }
        
        res = requests.get(
            'https://api.weixin.qq.com/cgi-bin/ticket/getticket',
            params=params,
            timeout=10
        )
        
        if res.status_code != 200:
            app.logger.error(f"[WECHAT] 获取jsapi_ticket HTTP错误: {res.status_code}")
            return None
            
        result = res.json()
        if 'ticket' in result:
            app.logger.info(f"[WECHAT] 成功获取新jsapi_ticket: {result['ticket'][:10]}...")
            return result['ticket']
        else:
            error_code = result.get('errcode', 'unknown')
            error_msg = result.get('errmsg', 'unknown error')
            app.logger.error(f"[WECHAT] 获取jsapi_ticket失败: code={error_code}, msg={error_msg}")
            
            return None
            
    except Exception as e:
        app.logger.error(f"[WECHAT] 请求jsapi_ticket异常: {str(e)}")
        return None

def get_wechat_jsapi_ticket(force_refresh=False):
    """
    获取微信 jsapi_ticket，优先从缓存获取，过期或强制刷新时重新获取并缓存
    
    Args:
        force_refresh: 是否强制刷新，即使缓存中有效
        
    Returns:
        jsapi_ticket: 微信 jsapi_ticket
    """
    try:
        # 获取 Redis 连接
        redis_url = app.config.get("REDIS_BROKER_URL") or os.getenv("REDIS_BROKER_URL")
        if not redis_url:
            app.logger.error("[WECHAT] Redis连接配置未找到，无法缓存jsapi_ticket")
            return _request_new_jsapi_ticket()  # 无法缓存时直接请求
            
        redis_conn = redis.Redis.from_url(redis_url)
        
        # 定义Redis中存储 jsapi_ticket 的键名
        jsapi_ticket_key = "wechat:jsapi_ticket"
        
        # 如果不强制刷新，尝试从Redis获取缓存的ticket
        if not force_refresh:
            ticket_data = redis_conn.get(jsapi_ticket_key)
            if ticket_data:
                ticket_info = json.loads(ticket_data)
                # 检查是否即将过期（留10分钟缓冲）
                now = time.time()
                if ticket_info['expires_at'] > now + 600:
                    app.logger.debug(f"[WECHAT] 使用缓存的jsapi_ticket，还有{int(ticket_info['expires_at']-now)}秒过期")
                    return ticket_info['ticket']
                else:
                    app.logger.info("[WECHAT] jsapi_ticket即将过期，准备刷新")
        
        # 如果缓存不存在、已过期或强制刷新，则重新获取
        jsapi_ticket = _request_new_jsapi_ticket()
        if jsapi_ticket:
            # 保存到Redis，设置过期时间比官方少10分钟，确保安全更新
            expires_in = 7200  # 标准过期时间2小时
            expires_at = time.time() + expires_in
            
            ticket_info = {
                'ticket': jsapi_ticket,
                'created_at': time.time(),
                'expires_at': expires_at
            }
            
            # 存储到Redis，设置过期时间为原始过期时间
            redis_conn.setex(
                jsapi_ticket_key,
                time=expires_in,
                value=json.dumps(ticket_info)
            )
            
            app.logger.info(f"[WECHAT] 成功刷新jsapi_ticket，将在{datetime.fromtimestamp(expires_at).strftime('%Y-%m-%d %H:%M:%S')}过期")
            return jsapi_ticket
        else:
            app.logger.error("[WECHAT] 获取jsapi_ticket失败")
            # 失败时尝试使用旧ticket（如果存在）
            old_ticket_data = redis_conn.get(jsapi_ticket_key)
            if old_ticket_data:
                old_ticket_info = json.loads(old_ticket_data)
                app.logger.warning("[WECHAT] 使用可能已过期的jsapi_ticket作为备用")
                return old_ticket_info['ticket']
            return None
            
    except Exception as e:
        app.logger.error(f"[WECHAT] 处理jsapi_ticket时出错: {str(e)}")
        return _request_new_jsapi_ticket()  # 错误时直接请求新ticket

def get_wechat_qrcode_url(ticket):
    """
    根据微信ticket获取二维码图片URL
    
    Args:
        ticket: 微信生成的二维码ticket
        
    Returns:
        qrcode_url: 二维码图片URL，可直接在前端img标签使用
    """
    try:
        if not ticket:
            app.logger.error("[WECHAT] 无法生成二维码URL：ticket为空")
            return None
            
        # 对ticket进行URL编码
        encoded_ticket = urllib.parse.quote(ticket)
        
        # 拼接微信二维码URL
        qrcode_url = f"https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket={encoded_ticket}"
        
        app.logger.debug(f"[WECHAT] 生成二维码URL成功: {qrcode_url[:50]}...")
        return qrcode_url
        
    except Exception as e:
        app.logger.error(f"[WECHAT] 生成二维码URL错误: {str(e)}")
        return None

def generate_wechat_qrcode(scene_str=None, expire_seconds=None):
    """
    生成微信二维码
    
    Args:
        scene_str: 场景值字符串，用于后续识别用户，如果为None则使用临时UUID
        expire_seconds: 过期时间（秒），不传则默认为永久二维码
        
    Returns:
        dict: 包含ticket和url的字典，如{'ticket': 'xxx', 'url': 'https://...'}
    """
    try:
        # 重置上次错误
        if hasattr(app, 'last_wx_error'):
            app.last_wx_error = None
            
        access_token = get_wechat_access_token()
        if not access_token:
            app.logger.error("[WECHAT] 无法获取access_token，无法生成二维码")
            return None
            
        # 如果没有传入场景值，生成一个随机字符串
        if not scene_str:
            import uuid
            scene_str = str(uuid.uuid4()).replace('-', '')[:16]
            
        # 构建请求参数，区分临时和永久二维码
        qrcode_url = "https://api.weixin.qq.com/cgi-bin/qrcode/create"
        params = {"access_token": access_token}
        
        # 根据是否有过期时间决定是临时还是永久二维码
        if expire_seconds:
            # 临时二维码
            data = {
                "expire_seconds": expire_seconds,
                "action_name": "QR_STR_SCENE",
                "action_info": {"scene": {"scene_str": scene_str}}
            }
        else:
            # 永久二维码
            data = {
                "action_name": "QR_LIMIT_STR_SCENE",
                "action_info": {"scene": {"scene_str": scene_str}}
            }
            
        # 发送请求
        res = requests.post(
            qrcode_url,
            params=params,
            json=data,
            timeout=10
        )
        
        if res.status_code != 200:
            app.logger.error(f"[WECHAT] 获取二维码ticket HTTP错误: {res.status_code}")
            return None
            
        result = res.json()
        if 'ticket' in result:
            ticket = result['ticket']
            qrcode_url = get_wechat_qrcode_url(ticket)
            
            response = {
                'ticket': ticket,
                'url': qrcode_url,
                'expire_seconds': expire_seconds,
                'scene_str': scene_str
            }
            
            app.logger.info(f"[WECHAT] 成功生成二维码，场景值: {scene_str}")
            return response
        else:
            error_code = result.get('errcode', 'unknown')
            error_msg = result.get('errmsg', 'unknown error')
            app.logger.error(f"[WECHAT] 获取二维码ticket失败: code={error_code}, msg={error_msg}")
            return None
            
    except Exception as e:
        app.logger.error(f"[WECHAT] 生成二维码异常: {str(e)}")
        return None

def get_wechat_user_info(openid):
    """
    获取微信用户的基本信息
    
    Args:
        openid: 用户的OpenID
        
    Returns:
        dict: 包含用户信息的字典，如果获取失败则为None
    """
    try:
        # 先获取access_token
        access_token = get_wechat_access_token()
        if not access_token:
            app.logger.error("[WECHAT] 无法获取access_token，无法获取用户信息")
            return None
            
        # 构建请求
        api_url = f"https://api.weixin.qq.com/cgi-bin/user/info"
        params = {
            'access_token': access_token,
            'openid': openid,
            'lang': 'zh_CN'
        }
        
        app.logger.debug(f"[WECHAT] 请求用户信息, openid: {openid[:5]}...")
        
        # 发送请求
        res = requests.get(api_url, params=params, timeout=10)
        
        if res.status_code != 200:
            app.logger.error(f"[WECHAT] 获取用户信息HTTP错误: {res.status_code}")
            return None
            
        result = res.json()
        if 'errcode' in result and result['errcode'] != 0:
            app.logger.error(f"[WECHAT] 获取用户信息失败: code={result['errcode']}, msg={result.get('errmsg')}")
            return None
            
        app.logger.info(f"[WECHAT] 成功获取用户信息: {openid[:5]}...")
        app.logger.debug(f"[WECHAT] 用户信息: {result}")
        return result
        
    except Exception as e:
        app.logger.error(f"[WECHAT] 获取用户信息异常: {str(e)}")
        return None