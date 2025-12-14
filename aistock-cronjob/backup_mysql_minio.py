import subprocess
import gzip
import boto3
import datetime
import os
import tempfile
from dotenv import load_dotenv

load_dotenv(override=True)

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")

BACKUP_DIR = os.getenv("BACKUP_DIR", "/tmp/db_backups")


def run_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    sql_path = os.path.join(BACKUP_DIR, f"{DB_NAME}_{timestamp}.sql")
    gz_path = sql_path + ".gz"

    print(f"📦 开始备份数据库 {DB_NAME} -> {gz_path}")

    # 使用环境变量传密码，避免在命令行中暴露或误写引号
    env = os.environ.copy()
    if DB_PASS:
        env["MYSQL_PWD"] = DB_PASS

    dump_cmd = [
        "mysqldump",
        "-h", DB_HOST,
        "-u", DB_USER,
        "--single-transaction",
        "--quick",
        "--routines",
        "--triggers",
        "--databases", DB_NAME,
        "--ssl=0"
    ]

    # 先把 mysqldump 输出写入临时 .sql 文件（避免一次性占用内存）
    try:
        with open(sql_path, "wb") as sql_file:
            result = subprocess.run(
                dump_cmd,
                stdout=sql_file,
                stderr=subprocess.PIPE,
                env=env
            )
        if result.returncode != 0:
            err = result.stderr.decode(errors="replace")
            print("❌ mysqldump 失败，returncode:", result.returncode)
            print("❌ stderr:", err)
            # 清理可能存在的不完整文件
            if os.path.exists(sql_path):
                os.remove(sql_path)
            return None

        # 压缩
        with open(sql_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            while True:
                chunk = f_in.read(8192)
                if not chunk:
                    break
                f_out.write(chunk)
        # 删除原始 .sql 文件
        os.remove(sql_path)
        print("✅ 数据库备份成功")
    except FileNotFoundError as e:
        print("❌ 找不到 mysqldump，可执行文件未安装或不在 PATH：", e)
        return None
    except Exception as e:
        print("❌ 备份过程中出错:", e)
        # 尝试清理临时文件
        if os.path.exists(sql_path):
            os.remove(sql_path)
        if os.path.exists(gz_path):
            os.remove(gz_path)
        return None

    # 上传到 MinIO
    try:
        from botocore.config import Config
        s3 = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            config=Config(s3={'addressing_style': 'path'})
        )

        object_name = os.path.basename(gz_path)
        s3.upload_file(gz_path, BUCKET_NAME, object_name)
        print(f"✅ 已上传到 MinIO: {BUCKET_NAME}/{object_name}")

        # 上传成功后删除本地临时文件
        os.remove(gz_path)
        return object_name
    except Exception as e:
        print("❌ 上传 MinIO 失败:", e)
        # 保留本地文件以便排查
        return None


if __name__ == "__main__":
    run_backup()
