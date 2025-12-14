from flask import Blueprint, jsonify, request, current_app as app, Response
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
import requests
from datetime import datetime, timedelta
from db.models import db, User, UserStock
import uuid
from utils.wx_utils import generate_wechat_qrcode, get_wechat_user_info
import hashlib
import xml.etree.ElementTree as ET
from sqlalchemy.exc import ProgrammingError, OperationalError
import re
import base64
# 导入Redis缓存工具
from utils.redis_cache import (
    save_scan_login_state, get_scan_login_state, 
    update_scan_login_state, delete_scan_login_state, 
    list_all_scan_states
)
# 导入MinIO工具
try:
    from utils.minio_utils import upload_base64_image
except ImportError:
    app.logger.warning("未找到MinIO工具，头像上传功能将受限")
    upload_base64_image = None

# 创建蓝图
user_bp = Blueprint("user", __name__, url_prefix="/api")

# 微信登录接口
@user_bp.route("/auth/login", methods=["POST"])
def login():
    app.logger.debug("进入 /auth/login 接口")
    try:
        # 验证请求数据
        data = request.json
        app.logger.debug(f"请求数据: {data}")
        if not data or "code" not in data or not data.get("code"):
            return jsonify({"code": 400, "msg": "缺少必要参数code"}), 400

        code = data.get("code")
        app.logger.info(f"微信登录请求，code: {code[:10]}...")

        # 构建微信API请求
        wx_url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": app.config.get("WECHAT_APPID"),
            "secret": app.config.get("WECHAT_SECRET"),
            "js_code": code,
            "grant_type": "authorization_code",
        }

        # 记录环境变量检查（不含敏感信息）
        app.logger.debug(
            f"APPID长度: {len(params['appid']) if params['appid'] else 0}, SECRET已配置: {'是' if params['secret'] else '否'}"
        )

        # 请求微信API
        response = requests.get(wx_url, params=params, timeout=10)
        app.logger.debug(f"微信服务器响应状态码: {response.status_code}")
        app.logger.debug(f"微信服务器响应内容: {response.text}")

        if response.status_code != 200:
            app.logger.error(f"微信服务器HTTP错误: {response.status_code}")
            return (
                jsonify(
                    {"code": 500, "msg": f"微信服务器响应错误: {response.status_code}"}
                ),
                500,
            )

        # 解析响应
        try:
            res = response.json()
        except ValueError:
            app.logger.error(f"解析微信响应JSON失败: {response.text}")
            return jsonify({"code": 500, "msg": "无法解析微信服务器响应"}), 500

        # 输出详细的微信响应日志（生产环境应移除敏感信息）
        if "errcode" in res and res["errcode"] != 0:
            error_msg = (
                f"微信登录失败: code {res.get('errcode')}, msg: {res.get('errmsg')}"
            )
            app.logger.warning(error_msg)

            # 特定错误码的处理
            if res.get("errcode") == 40029:
                app.logger.warning(f"无效的code: {code[:10]}..., 可能已过期或被使用过")
                return (
                    jsonify(
                        {
                            "code": 401,
                            "msg": "登录失败: 微信授权码无效，请重新进入小程序获取",
                            "detail": "微信code已过期或已被使用，需要重新获取",
                            "action": "relogin",
                            "wx_error": res,
                        }
                    ),
                     401,
                )
            elif res.get("errcode") == 40163:
                return (
                    jsonify(
                        {
                            "code": 401,
                            "msg": "登录失败: code已被使用，请重新获取",
                            "wx_error": res,
                        }
                    ),
                    401,
                )
            elif res.get("errcode") == 41008:
                return (
                    jsonify(
                        {"code": 401, "msg": "登录失败: 缺少code参数", "wx_error": res}
                    ),
                    401,
                )
            elif res.get("errcode") == -1:
                return (
                    jsonify(
                        {
                            "code": 503,
                            "msg": "登录失败: 微信服务器繁忙，请稍后再试",
                            "wx_error": res,
                        }
                    ),
                    503,
                )
            else:
                return (
                    jsonify(
                        {
                            "code": 401,
                            "msg": f"登录失败: {res.get('errmsg', '未知错误')}",
                            "wx_error": res,
                        }
                    ),
                    401,
                )

        if "openid" not in res:
            app.logger.error(f"微信返回数据中没有openid: {res}")
            return (
                jsonify(
                    {
                        "code": 401,
                        "msg": "登录失败，微信未返回用户标识",
                        "wx_error": res,
                    }
                ),
                401,
            )

        # 记录成功的响应
        app.logger.info(f"微信登录成功，获取到openid: {res['openid'][:5]}...")

        # 更新用户信息 - 使用事务保证数据一致性
        try:
            openid = res["openid"]
            session_key = res.get("session_key")
            unionid = res.get("unionid")

            # 创建或更新用户
            user = User.query.filter_by(openid=openid).first()
            if not user:
                app.logger.info(f"创建新用户, openid: {openid[:5]}...")
                user = User(openid=openid, session_key=session_key, unionid=unionid)
                db.session.add(user)
            else:
                app.logger.info(f"更新现有用户, ID: {user.id}")
                user.session_key = session_key
                if unionid and not user.unionid:
                    user.unionid = unionid
                user.updated_at = datetime.now()

            db.session.commit()

            # 生成JWT令牌
            expires = timedelta(days=30)  # 令牌有效期30天
            access_token = create_access_token(
                identity=str(user.id),
                expires_delta=expires,
                additional_claims={"role": user.role},
            )

            return jsonify(
                {
                    "code": 0,
                    "token": access_token,
                    "user_id": user.id,
                    "expires_in": expires.total_seconds(),
                }
            )

        except Exception as db_error:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {str(db_error)}")
            return jsonify({"code": 500, "msg": "用户数据处理失败"}), 500

    except requests.RequestException as e:
        app.logger.error(f"请求微信API网络错误: {str(e)}")
        return jsonify({"code": 500, "msg": f"网络请求失败: {str(e)}"}), 500
    except Exception as e:
        app.logger.error(f"登录过程发生未预期错误: {str(e)}")
        return jsonify({"code": 500, "msg": "服务器内部错误"}), 500


# 用户信息接口 - 获取当前登录用户的信息
@user_bp.route("/user/info", methods=["GET"])
@jwt_required()
def get_user_info():
    try:
        # 获取当前登录用户ID
        user_id = get_jwt_identity()

        # 查询用户信息
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "msg": "用户不存在"}), 404

        # 查询用户的自选股数量
        stocks_count = UserStock.query.filter_by(user_id=user_id).count()

        # 构建并返回用户数据（不包括敏感信息）
        return jsonify(
            {
                "code": 0,
                "data": {
                    "user_id": user.id,
                    "nickname": user.nickname,
                    "avatar_url": user.avatar_url,
                    "role": user.role,
                    "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "stocks_count": stocks_count,
                },
            }
        )
    except Exception as e:
        app.logger.error(f"获取用户信息失败: {str(e)}")
        return jsonify({"code": 500, "msg": "服务器内部错误"}), 500


def cleanup_expired_login_states():
    """清理过期的扫码登录状态，防止Redis中累积过多无效数据"""
    try:
        # 获取所有扫码状态
        all_states = list_all_scan_states()
        now = datetime.now()
        cleaned_count = 0
        
        # 检查并删除过期状态
        for scan_id, state_data in all_states.items():
            if "expires_at" in state_data:
                # 转换字符串格式的expires_at为datetime对象进行比较
                if isinstance(state_data["expires_at"], str):
                    try:
                        expires_at = datetime.fromisoformat(state_data["expires_at"])
                    except ValueError:
                        expires_at = datetime.strptime(state_data["expires_at"], "%Y-%m-%d %H:%M:%S.%f")
                else:
                    expires_at = state_data["expires_at"]
                    
                if now >= expires_at:
                    if delete_scan_login_state(scan_id):
                        cleaned_count += 1
                        
        if cleaned_count > 0:
            app.logger.info(f"[SCAN_LOGIN] 清理了 {cleaned_count} 个过期的扫码状态")
    except Exception as e:
        app.logger.error(f"[SCAN_LOGIN] 清理过期状态异常: {str(e)}")


@user_bp.route("/auth/scan-login-url", methods=["GET"])
def get_scan_login_url():
    """获取微信扫码登录的二维码"""
    try:
        # 清理过期状态
        cleanup_expired_login_states()
        
        # 检查必要配置是否存在
        if not app.config.get("WECHAT_SCAN_APPID"):
            app.logger.error("[SCAN_LOGIN] 缺少WECHAT_SCAN_APPID配置")
            return jsonify({
                "code": 500,
                "msg": "微信登录配置错误: 缺少AppID",
                "error_type": "config_missing"
            }), 500

        if not app.config.get("WECHAT_SCAN_SECRET"):
            app.logger.error("[SCAN_LOGIN] 缺少WECHAT_SCAN_SECRET配置")
            return jsonify({
                "code": 500,
                "msg": "微信登录配置错误: 缺少AppSecret",
                "error_type": "config_missing"
            }), 500

        # 生成唯一的state作为场景值和状态跟踪ID
        state = str(uuid.uuid4())
        app.logger.info(f"[SCAN_LOGIN] 生成新的state: {state}")

        # 通过微信工具函数生成二维码，场景值包含state以便后续识别
        try:
            qrcode_result = generate_wechat_qrcode(
                scene_str=f"login_{state}",
                expire_seconds=300  # 5分钟过期
            )
            app.logger.info(f"[SCAN_LOGIN] 二维码生成完成，准备保存状态: {state}")
        except Exception as qr_error:
            app.logger.error(f"[SCAN_LOGIN] 生成二维码异常: {str(qr_error)}")
            return jsonify({
                "code": 500,
                "msg": f"生成二维码失败: {str(qr_error)}",
                "error_type": "qrcode_generation_failed"
            }), 500

        if not qrcode_result or "url" not in qrcode_result:
            app.logger.error(f"[SCAN_LOGIN] 生成微信二维码失败")
            # 获取更详细的错误信息
            error_msg = "生成二维码失败，请检查微信公众平台配置"
            if hasattr(app, 'last_wx_error') and app.last_wx_error:
                error_msg = f"微信错误: {app.last_wx_error}"

            return jsonify({
                "code": 500,
                "msg": error_msg,
                "error_type": "wx_api_error"
            }), 500

        # 存储登录状态信息 - 使用Redis替代内存字典
        try:
            # 准备要缓存的状态数据
            state_data = {
                "status": "pending",
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(minutes=5),
                "scene_str": qrcode_result.get("scene_str"),
                "ticket": qrcode_result.get("ticket")
            }
            
            # 保存到Redis
            if not save_scan_login_state(state, state_data, expire_seconds=300):
                raise Exception("无法保存登录状态到Redis")
                
            app.logger.info(f"[SCAN_LOGIN] 状态已保存到Redis: {state}")
        except Exception as state_error:
            app.logger.error(f"[SCAN_LOGIN] 保存状态时异常: {str(state_error)}")
            return jsonify({
                "code": 500,
                "msg": "服务器内部错误，无法保存登录状态",
                "error_type": "state_save_failed"
            }), 500

        # 返回二维码信息和状态ID
        return jsonify({
            "code": 0,
            "qrcode_url": qrcode_result["url"],  # 直接返回可用的二维码图片URL
            "state": state,  # 只返回一个ID，避免混淆
            "expires_in": 300  # 5分钟有效期
        })

    except Exception as e:
        app.logger.error(f"[SCAN_LOGIN] 生成登录二维码异常: {str(e)}")
        return jsonify({"code": 500, "msg": "服务器内部错误，请稍后再试"}), 500


@user_bp.route("/auth/wx-event", methods=["GET", "POST"])
def wechat_verify():
    """处理微信服务器验证请求和消息推送
    GET: 处理服务器配置验证
    POST: 处理微信消息推送
    """
    app.logger.info(f"[WECHAT] 收到微信请求: {request.method}")
    if request.method == "POST":
        xml_data = request.data
        if not xml_data:
            return "success"  # 即使出错也返回success避免微信服务器重试
        try:
            root = ET.fromstring(xml_data)
            msg_type = root.find("MsgType").text if root.find("MsgType") is not None else None
            event = root.find("Event").text if root.find("Event") is not None else None
            openid = root.find("FromUserName").text if root.find("FromUserName") is not None else None
            app.logger.info(f"[WECHAT_EVENT] 处理事件类型: {event}, OpenID: {openid[:5]}...")
            if not openid:
                app.logger.error("[WECHAT_EVENT] 事件中没有OpenID")
                return "success"

            if msg_type == "event" and event == "subscribe":
                app.logger.info(f"[WECHAT_EVENT] 用户 {openid[:5]}... 关注了公众号")
                try:
                    user = User.query.filter_by(openid=openid).first()
                    scene_str = None
                    event_key = root.find("EventKey").text if root.find("EventKey") is not None else None
                    if event_key and event_key.startswith("qrscene_"):
                        scene_str = event_key[8:]  # 移除前缀'qrscene_'
                        app.logger.info(f"[WECHAT_EVENT] 扫描带参二维码关注, 场景: {scene_str}")
                    if not user:
                        app.logger.info(f"[WECHAT_EVENT] 创建新用户记录 OpenID: {openid[:5]}...")
                        user = User(
                            openid=openid,
                            subscribe=True,
                            subscribe_time=datetime.now(),
                            subscribe_scene=scene_str or "normal_subscribe",
                        )
                        db.session.add(user)
                    else:
                        app.logger.info(f"[WECHAT_EVENT] 更新用户关注状态 ID: {user.id}")
                        user.subscribe = True
                        user.subscribe_time = datetime.now()
                        if scene_str:
                            user.subscribe_scene = scene_str
                    user_info = get_wechat_user_info(openid)
                    if user_info:
                        if 'nickname' in user_info and user_info['nickname']:
                            user.nickname = user_info['nickname']
                        if 'headimgurl' in user_info and user_info['headimgurl']:
                            user.avatar_url = user_info['headimgurl']
                    db.session.commit()
                    if scene_str and scene_str.startswith("login_"):
                        handle_scan_login(scene_str, openid, user)
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"[WECHAT_EVENT] 处理关注事件数据库操作失败: {str(e)}")
            elif msg_type == "event" and event == "unsubscribe":
                app.logger.info(f"[WECHAT_EVENT] 用户 {openid[:5]}... 取消关注了公众号")
                try:
                    user = User.query.filter_by(openid=openid).first()
                    if user:
                        user.subscribe = False
                        db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    app.logger.error(f"[WECHAT_EVENT] 处理取消关注事件失败: {str(e)}")
            elif msg_type == "event" and event == "SCAN":
                app.logger.info(f"[WECHAT_EVENT] 已关注用户 {openid[:5]}... 扫码")
                scene_str = root.find("EventKey").text if root.find("EventKey") is not None else None
                if scene_str and scene_str.startswith("login_"):
                    try:
                        user = User.query.filter_by(openid=openid).first()
                        if not user:
                            app.logger.warning(f"[WECHAT_EVENT] 已关注用户扫码但数据库中不存在: {openid[:5]}...")
                            user = User(
                                openid=openid,
                                subscribe=True,
                                subscribe_time=datetime.now(),
                                subscribe_scene="direct_scan",
                            )
                            db.session.add(user)
                            db.session.commit()
                            user_info = get_wechat_user_info(openid)
                            if user_info:
                                if 'nickname' in user_info and user_info['nickname']:
                                    user.nickname = user_info['nickname']
                                if 'headimgurl' in user_info and user_info['headimgurl']:
                                    user.avatar_url = user_info['headimgurl']
                                db.session.commit()
                        handle_scan_login(scene_str, openid, user)
                    except Exception as e:
                        db.session.rollback()
                        app.logger.error(f"[WECHAT_EVENT] 处理扫码事件失败: {str(e)}")
            return "success"
        except ET.ParseError as xml_error:
            app.logger.error(f"[WECHAT_EVENT] 解析微信XML失败: {str(xml_error)}")
            return "success"
        except Exception as e:
            app.logger.error(f"[WECHAT_EVENT] 处理微信事件异常: {str(e)}")
            db.session.rollback()
            return "success"
    elif request.method == "GET":
        signature = request.args.get('signature')
        timestamp = request.args.get('timestamp')
        nonce = request.args.get('nonce')
        echostr = request.args.get('echostr')
        if not all([signature, timestamp, nonce, echostr]):
            app.logger.warning("[WECHAT_VERIFY] 微信验证参数不完整")
            return "参数错误", 400
        token = app.config.get('WECHAT_SCAN_TOKEN')
        if not token:
            app.logger.error("[WECHAT_VERIFY] 缺少 WECHAT_SCAN_TOKEN 配置")
            return "配置错误", 500
        temp_list = [token, timestamp, nonce]
        temp_list.sort()
        temp_str = ''.join(temp_list)
        hash_obj = hashlib.sha1()
        hash_obj.update(temp_str.encode('utf-8'))
        hashcode = hash_obj.hexdigest()
        app.logger.debug(f"[WECHAT_VERIFY] 计算的签名: {hashcode}")
        if hashcode == signature:
            app.logger.info("[WECHAT_VERIFY] 微信服务器验证成功")
            return echostr
        else:
            app.logger.warning("[WECHAT_VERIFY] 微信服务器验证失败")
            return "验证失败", 403
    else:
        return "方法不允许", 405


def handle_scan_login(scene_str, openid, user):
    """处理用户扫码登录的逻辑
    Args:
        scene_str: 场景值字符串，格式为 "login_<state>"
        openid: 用户的微信OpenID
        user: 用户对象
    """
    try:
        if not scene_str.startswith("login_"):
            app.logger.warning(f"[SCAN_LOGIN] 无效的扫码场景值: {scene_str}")
            return False
        state = scene_str[6:]
        app.logger.debug(f"[SCAN_LOGIN] 处理扫码登录，state: {state}, 用户ID: {user.id}")
        
        # 从Redis中获取状态
        login_state = get_scan_login_state(state)
        if not login_state:
            app.logger.warning(f"[SCAN_LOGIN] 未找到状态记录: {state}")
            return False
            
        if login_state.get("status") != "pending":
            app.logger.warning(f"[SCAN_LOGIN] 状态不是等待中: {login_state.get('status')}")
            return False
            
        # 检查是否过期
        if isinstance(login_state.get("expires_at"), str):
            try:
                expires_at = datetime.fromisoformat(login_state.get("expires_at"))
            except ValueError:
                expires_at = datetime.strptime(login_state.get("expires_at"), "%Y-%m-%d %H:%M:%S.%f")
        else:
            expires_at = login_state.get("expires_at")
            
        if datetime.now() >= expires_at:
            app.logger.warning(f"[SCAN_LOGIN] 状态已过期: {state}")
            delete_scan_login_state(state)
            return False
            
        # 生成Token
        expires = timedelta(days=30)
        jwt_token = create_access_token(
            identity=str(user.id),
            expires_delta=expires,
            additional_claims={"role": user.role or "user"},
        )
        app.logger.info(f"[SCAN_LOGIN] 成功生成token，用户ID: {user.id}, token长度: {len(jwt_token) if jwt_token else 0}")
        
        # 更新状态到Redis
        login_state.update({
            "status": "confirmed",
            "token": jwt_token,
            "expires_in": expires.total_seconds(),
            "user_id": user.id,
            "updated_at": datetime.now(),
            "openid": openid,
            "user_info": {
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "role": user.role
            }
        })
        
        if not update_scan_login_state(state, login_state, expire_seconds=300):
            app.logger.error(f"[SCAN_LOGIN] 更新Redis中的登录状态失败: {state}")
            return False
            
        app.logger.info(f"[SCAN_LOGIN] 用户 {user.id} 扫码登录成功 (state: {state})，状态已更新为confirmed")
        return True
    except Exception as e:
        app.logger.error(f"[SCAN_LOGIN] 处理扫码登录失败: {str(e)}")
        return False


@user_bp.route("/auth/login-status", methods=["GET"])
def check_login_status():
    """轮询扫码登录状态"""
    try:
        state = request.args.get('state')
        if not state:
            return jsonify({"code": 400, "msg": "缺少必要参数state"}), 400

        app.logger.debug(f"[SCAN_LOGIN] 检查登录状态, state: {state}")
        
        # 从Redis获取状态
        login_state = get_scan_login_state(state)
        if not login_state:
            app.logger.warning(f"[SCAN_LOGIN] 未找到状态记录: {state}")
            return jsonify({
                "code": 404, 
                "msg": "未找到对应的扫码状态，请重新获取二维码", 
                "status": "not_found"
            }), 404
            
        # 检查是否过期
        if isinstance(login_state.get("expires_at"), str):
            try:
                expires_at = datetime.fromisoformat(login_state.get("expires_at"))
            except ValueError:
                expires_at = datetime.strptime(login_state.get("expires_at"), "%Y-%m-%d %H:%M:%S.%f")
        else:
            expires_at = login_state.get("expires_at")
            
        if datetime.now() >= expires_at:
            delete_scan_login_state(state)
            app.logger.info(f"[SCAN_LOGIN] 状态已过期并被清理: {state}")
            return jsonify({
                "code": 401, 
                "msg": "扫码状态已过期，请重新获取二维码", 
                "status": "expired"
            }), 401
            
        status = login_state.get("status", "pending")
        app.logger.debug(f"[SCAN_LOGIN] 当前状态: {status}, state: {state}")
        
        if status == "pending":
            remaining = int((expires_at - datetime.now()).total_seconds())
            return jsonify({
                "code": 0,
                "status": "pending", 
                "msg": "等待扫码登录", 
                "remaining": remaining
            })
        elif status == "confirmed":
            token = login_state.get("token")
            user_id = login_state.get("user_id")
            app.logger.info(f"[SCAN_LOGIN] 返回扫码登录成功信息，用户ID: {user_id}, token长度: {len(token) if token else 0}")
            result = {
                "code": 0,
                "status": "confirmed", 
                "msg": "扫码登录成功",
                "token": token,
                "user_id": user_id,
                "expires_in": login_state.get("expires_in")
            }
            if login_state.get("user_info"):
                result["user_info"] = login_state.get("user_info")
            
            # 确认登录成功后，从Redis中删除状态
            delete_scan_login_state(state)
            app.logger.debug(f"[SCAN_LOGIN] 登录成功后清理状态: {state}")
            
            return jsonify(result)
        else:
            app.logger.error(f"[SCAN_LOGIN] 未知的状态: {status}, state: {state}")
            return jsonify({
                "code": 500, 
                "msg": f"未知的扫码状态: {status}", 
                "status": status
            }), 500
    except Exception as e:
        app.logger.error(f"[SCAN_LOGIN] 检查登录状态异常: {str(e)}")
        return jsonify({
            "code": 500, 
            "msg": "服务器内部错误", 
            "error": str(e)
        }), 500


# 修改个人信息接口
@user_bp.route("/user/profile", methods=["POST"])
@jwt_required()
def update_user_profile():
    """修改用户个人信息"""
    try:
        app.logger.debug(f"[USER_PROFILE] 进入接口，JWT 认证通过，用户 ID: {get_jwt_identity()}")
        user_id = get_jwt_identity()
        app.logger.debug(f"[USER_PROFILE] 当前用户 ID 解析为: {user_id}")
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "msg": "用户不存在"}), 404
        data = request.json
        app.logger.debug(f"[USER_PROFILE] 接收到的请求数据: {data}")
        if not data:
            return jsonify({"code": 400, "msg": "请求数据不能为空"}), 400
        original_nickname = user.nickname
        original_avatar = user.avatar_url
        if "nickname" in data and data["nickname"] is not None:
            nickname = data["nickname"].strip()
            if len(nickname) > 30:
                return jsonify({"code": 400, "msg": "昵称不能超过30个字符"}), 400
            user.nickname = nickname
            app.logger.debug(f"[USER_PROFILE] 用户 {user_id} 昵称已更新: {original_nickname} -> {nickname}")
        if "avatar_url" in data and data["avatar_url"] is not None:
            avatar_url = data["avatar_url"]
            if avatar_url.startswith(('http://', 'https://')):
                user.avatar_url = avatar_url
                app.logger.debug(f"[USER_PROFILE] 用户 {user_id} 头像URL已更新")
            else:
                if upload_base64_image:
                    is_base64 = False
                    try:
                        if "base64," in avatar_url:
                            is_base64 = True
                        else:
                            base64.b64decode(avatar_url)
                            is_base64 = True
                    except:
                        is_base64 = False
                    if is_base64:
                        uploaded_url = upload_base64_image(avatar_url)
                        if uploaded_url:
                            user.avatar_url = uploaded_url
                            app.logger.info(f"[USER_PROFILE] 用户 {user_id} 头像已上传到MinIO: {uploaded_url}")
                        else:
                            return jsonify({"code": 500, "msg": "头像上传失败"}), 500
                    else:
                        return jsonify({"code": 400, "msg": "头像格式无效，请提供有效的URL或Base64编码"}), 400
                else:
                    return jsonify({"code": 501, "msg": "服务器不支持Base64头像上传，请提供图片URL"}), 501
        try:
            db.session.commit()
            app.logger.info(f"[USER_PROFILE] 用户 {user_id} 个人信息已更新")
            return jsonify({
                "code": 0,
                "msg": "个人信息更新成功",
                "data": {
                    "user_id": user.id,
                    "nickname": user.nickname,
                    "avatar_url": user.avatar_url,
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            })
        except Exception as db_error:
            db.session.rollback()
            app.logger.error(f"[USER_PROFILE] 保存用户信息失败: {str(db_error)}")
            return jsonify({"code": 500, "msg": "保存用户信息失败"}), 500
    except Exception as e:
        app.logger.error(f"[USER_PROFILE] 更新个人信息异常: {str(e)}")
        return jsonify({"code": 500, "msg": "服务器内部错误"}), 500