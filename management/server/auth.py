import jwt
import os
from functools import wraps
from flask import request, jsonify

# 直接从环境变量读取 JWT_SECRET，避免循环导入
JWT_SECRET = os.getenv("MANAGEMENT_JWT_SECRET", "your-secret-key")

# 这个f用于接收试图函数，即被修饰的那个函数
def token_required(f):
    """
    暂时没有用到这个装饰器
    Token 验证装饰器
    使用方式: @token_required
    只验证 token 是否有效，不检查权限
    """
    # 定义一个新的函数
    @wraps(f)
    def decorated(*args, **kwargs):
        # 从请求头获取 token
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return jsonify({
                "code": 401,
                "message": "缺少认证令牌"
            }), 401

        # 提取 Bearer token
        try:
            token = auth_header.replace('Bearer ', '')
        except:
            return jsonify({
                "code": 401,
                "message": "无效的令牌格式"
            }), 401

        # 验证并解码 token
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

            # 将用户信息保存到 request 对象中，供后续使用
            request.user = {
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "is_superuser": payload.get("is_superuser"),
                "is_system": payload.get("is_system")
            }

        except jwt.ExpiredSignatureError:
            return jsonify({
                "code": 401,
                "message": "令牌已过期"
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "code": 401,
                "message": "无效令牌"
            }), 401

        return f(*args, **kwargs)

    # 用新的函数替换到原来的函数
    return decorated


def require_superuser(f):
    """
    要求超级用户权限的装饰器
    验证 token + is_superuser = 1
    用于：普通教师可访问的接口
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 先验证 token
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"code": 401, "message": "缺少认证令牌"}), 401

        try:
            token = auth_header.replace('Bearer ', '')
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

            if payload.get("is_superuser") != 1:
                return jsonify({
                    "code": 403,
                    "message": "需要教师权限"
                }), 403

            request.user = {
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "is_superuser": payload.get("is_superuser"),
                "is_system": payload.get("is_system")
            }

        except jwt.ExpiredSignatureError:
            return jsonify({"code": 401, "message": "令牌已过期"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"code": 401, "message": "无效令牌"}), 401

        return f(*args, **kwargs)

    return decorated


def require_system_admin(f):
    """
    要求系统超级管理员权限的装饰器
    验证 token + is_superuser = 1 且 is_system = 1
    用于：教师管理等只有系统管理员才能操作的接口
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 先验证 token
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"code": 401, "message": "缺少认证令牌"}), 401

        try:
            token = auth_header.replace('Bearer ', '')
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

            # 检查是否是系统超级管理员 (is_superuser=1 且 is_system=1)
            if payload.get("is_superuser") != 1 or payload.get("is_system") != 1:
                return jsonify({
                    "code": 403,
                    "message": "需要系统超级管理员权限"
                }), 403

            request.user = {
                "user_id": payload.get("user_id"),
                "username": payload.get("username"),
                "is_superuser": payload.get("is_superuser"),
                "is_system": payload.get("is_system")
            }

        except jwt.ExpiredSignatureError:
            return jsonify({"code": 401, "message": "令牌已过期"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"code": 401, "message": "无效令牌"}), 401

        return f(*args, **kwargs)

    return decorated


def get_current_user():
    """
    获取当前登录用户信息
    在使用了认证装饰器的接口中调用
    返回: {
        "user_id": "...",
        "username": "...",
        "is_superuser": 1/0,
        "is_system": 1/0
    }
    """
    return getattr(request, 'user', None)
