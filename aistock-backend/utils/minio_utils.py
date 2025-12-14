import os
import io
import uuid
import base64
import logging
from datetime import timedelta
from minio import Minio
from flask import current_app as app

logger = logging.getLogger(__name__)

def get_minio_client():
    """
    获取MinIO客户端连接
    """
    try:
        minio_endpoint = os.getenv("MINIO_ENDPOINT") or app.config.get("MINIO_ENDPOINT")
        minio_access_key = os.getenv("MINIO_ACCESS_KEY") or app.config.get("MINIO_ACCESS_KEY")
        minio_secret_key = os.getenv("MINIO_SECRET_KEY") or app.config.get("MINIO_SECRET_KEY")
        
        if not all([minio_endpoint, minio_access_key, minio_secret_key]):
            logger.error("MinIO配置缺失，无法创建客户端")
            return None
        
        # 创建MinIO客户端
        client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=minio_endpoint.startswith("https")  # 根据endpoint判断是否使用SSL
        )
        
        return client
    except Exception as e:
        logger.error(f"创建MinIO客户端失败: {str(e)}")
        return None

def ensure_bucket_exists(bucket_name="aistock-avatars"):
    """确保存储桶存在，不存在则创建"""
    try:
        client = get_minio_client()
        if not client:
            return False
        
        # 检查存储桶是否存在
        if not client.bucket_exists(bucket_name):
            # 创建存储桶
            client.make_bucket(bucket_name)
            logger.info(f"已创建MinIO存储桶: {bucket_name}")
            
            # 设置公共读取策略
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                    }
                ]
            }
            client.set_bucket_policy(bucket_name, policy)
            
        return True
    except Exception as e:
        logger.error(f"确认MinIO存储桶失败: {str(e)}")
        return False

def upload_base64_image(base64_data, bucket_name="aistock-avatars"):
    """
    将Base64编码的图片上传到MinIO
    
    Args:
        base64_data: 不包含前缀的Base64字符串 (如果有前缀如"data:image/jpeg;base64,"将自动去除)
        bucket_name: MinIO存储桶名称
        
    Returns:
        str: 上传成功返回完整的URL，失败返回None
    """
    try:
        # 确保bucket存在
        if not ensure_bucket_exists(bucket_name):
            return None
        
        # 去除可能的base64前缀
        if "base64," in base64_data:
            _, base64_data = base64_data.split("base64,", 1)
        
        # 解码Base64数据
        image_data = base64.b64decode(base64_data)
        
        # 创建文件对象
        file_obj = io.BytesIO(image_data)
        
        # 确定文件后缀（根据前缀判断或默认为jpg）
        file_ext = "jpg"  # 默认后缀
        if "image/png" in base64_data:
            file_ext = "png"
        elif "image/gif" in base64_data:
            file_ext = "gif"
        
        # 生成唯一文件名
        file_name = f"{uuid.uuid4()}.{file_ext}"
        
        # 获取MinIO客户端
        client = get_minio_client()
        if not client:
            return None
        
        # 上传文件
        client.put_object(
            bucket_name=bucket_name,
            object_name=file_name,
            data=file_obj,
            length=len(image_data),
            content_type=f"image/{file_ext}"
        )
        
        # 获取文件访问URL
        minio_endpoint = os.getenv("MINIO_ENDPOINT") or app.config.get("MINIO_ENDPOINT")
        # 去除可能的http前缀用于构建URL
        if minio_endpoint.startswith("http://"):
            minio_endpoint = minio_endpoint[7:]
        elif minio_endpoint.startswith("https://"):
            minio_endpoint = minio_endpoint[8:]
        
        # 构建访问URL
        url = f"http://{minio_endpoint}/{bucket_name}/{file_name}"
        logger.info(f"成功上传图片到MinIO: {url}")
        
        return url
    except Exception as e:
        logger.error(f"上传图片到MinIO失败: {str(e)}")
        return None

def get_presigned_url(object_name, bucket_name="aistock-avatars", expires=3600):
    """
    获取对象的预签名URL
    
    Args:
        object_name: 对象名称
        bucket_name: 存储桶名称
        expires: 过期时间（秒）
        
    Returns:
        str: 预签名URL
    """
    try:
        client = get_minio_client()
        if not client:
            return None
            
        url = client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_name,
            expires=timedelta(seconds=expires)
        )
        
        return url
    except Exception as e:
        logger.error(f"获取预签名URL失败: {str(e)}")
        return None
