import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import jwt
from dotenv import load_dotenv
from flask import Flask, request
from flask_cors import CORS

# Werkzeug 会在解析大文件请求时先写临时文件。生产环境把临时目录放到
# 大容量 /data 盘，避免视频上传占满系统盘；本地开发仍使用系统默认目录。
production_temp_root = Path("/data/ragflow-video-transcode-work/http-tmp")
if production_temp_root.parent.is_dir() and os.access(production_temp_root.parent, os.W_OK):
    production_temp_root.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(production_temp_root)

from routes import register_routes

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docker", ".env"))

app = Flask(__name__)
# 启用CORS，允许前端访问
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization"]}})

# 注册所有路由
register_routes(app)

# 从环境变量获取配置
ADMIN_USERNAME = os.getenv("MANAGEMENT_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("MANAGEMENT_ADMIN_PASSWORD", "12345678")
JWT_SECRET = os.getenv("MANAGEMENT_JWT_SECRET", "your-secret-key")


# 设置日志目录和文件名
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "parser.log")

# 配置 logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),  # 同时也输出到控制台
    ],
)


# 生成token
def generate_token(user_id, username, is_superuser, is_system):
    # 设置令牌过期时间（24小时后过期）
    expire_time = datetime.utcnow() + timedelta(hours=24)

    # 生成令牌
    token = jwt.encode({
        "user_id": user_id,
        "username": username,
        "is_superuser": is_superuser,
        "is_system": is_system,
        "exp": expire_time
    }, JWT_SECRET, algorithm="HS256")

    return token


# 登录路由保留在主文件中
@app.route("/api/v1/auth/login", methods=["POST"])
def login():
    from database import get_db_connection
    from werkzeug.security import check_password_hash
    import base64

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return {"code": 1, "message": "用户名或密码不能为空"}, 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 支持用 email 或 nickname 登录
        query = """
        SELECT id, nickname, password, status, is_superuser, is_system
        FROM user
        WHERE nickname = %s
        LIMIT 1
        """
        cursor.execute(query, (username, ))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if not user:
            return {"code": 1, "message": "用户不存在"}, 400

        # 检查用户状态
        if user.get("status") != "1":
            return {"code": 1, "message": "用户已被禁用"}, 400

        if user.get("is_superuser") != 1:
            return {"code": 1, "message": "不是管理员或老师"}, 400

        # 验证密码（存储的是 generate_password_hash(base64_password)）
        stored_password = user.get("password")
        try:
            # 将输入的密码 base64 编码后，用 check_password_hash 验证
            base64_password = base64.b64encode(password.encode()).decode()
            if not check_password_hash(stored_password, base64_password):
                return {"code": 1, "message": "密码错误"}, 400
        except Exception as e:
            logging.error(f"密码验证错误: {str(e)}")
            return {"code": 1, "message": "密码验证失败"}, 400

        # 生成token
        token = generate_token(user["id"], user["nickname"], user.get("is_superuser", 0), user.get("is_system", 0))

        return {
            "code": 0,
            "data": {
                "token": token,
                "userInfo": {
                    "id": user["id"],
                    "username": user["nickname"],
                    "isSuperuser": bool(user.get("is_superuser", 0)),
                    "isSystem": bool(user.get("is_system", 0))
                }
            },
            "message": "登录成功"
        }

    except Exception as e:
        logging.error(f"登录错误: {str(e)}")
        return {"code": 1, "message": f"登录失败: {str(e)}"}, 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
