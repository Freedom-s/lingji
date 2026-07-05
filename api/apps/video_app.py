"""
Video Progress API — 视频观看进度追踪

GET  /v1/video/progress/<doc_id>  — 查询当前用户的观看进度
POST /v1/video/progress/report    — 上报播放进度（有效观看判定）
"""
from datetime import datetime

from flask import request
from flask_login import login_required, current_user

from api.db.db_models import StudentVideoProgress
from api.utils.api_utils import get_json_result, get_data_error_result
from api.utils import get_uuid


@manager.route("/progress/<doc_id>", methods=["GET"])  # noqa: F821
@login_required
def get_progress(doc_id):
    """获取当前用户对指定视频的观看进度"""
    student_id = current_user.id

    try:
        record = StudentVideoProgress.select().where(
            (StudentVideoProgress.student_id == student_id) &
            (StudentVideoProgress.doc_id == doc_id)
        ).first()

        if record:
            return get_json_result(data={
                "watched_seconds": record.watched_seconds,
                "total_duration": record.total_duration,
                "last_position": record.last_position,
                "is_completed": record.is_completed,
            })
        else:
            return get_json_result(data={
                "watched_seconds": 0,
                "total_duration": 0,
                "last_position": 0,
                "is_completed": False,
            })
    except Exception as e:
        return get_data_error_result(message=str(e))


@manager.route("/progress/report", methods=["POST"])
@login_required
def report_progress():
    """上报播放进度，后端做有效观看判定"""
    data = request.json
    if not data:
        return get_data_error_result(message="请求数据不能为空")

    doc_id = data.get("doc_id")
    position = data.get("position", 0)
    total_duration = data.get("total_duration", 0)
    playback_rate = data.get("playback_rate", 1.0)

    if not doc_id:
        return get_data_error_result(message="缺少 doc_id")

    student_id = current_user.id

    try:
        # 查已有记录
        record = StudentVideoProgress.select().where(
            (StudentVideoProgress.student_id == student_id) &
            (StudentVideoProgress.doc_id == doc_id)
        ).first()

        if not record:
            # 首次上报，创建记录
            record = StudentVideoProgress.create(
                id=get_uuid(),
                create_time=int(datetime.now().timestamp()),
                create_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                update_time=int(datetime.now().timestamp()),
                update_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                student_id=student_id,
                doc_id=doc_id,
                watched_seconds=0,
                total_duration=total_duration,
                last_position=0,
                is_completed=False,
            )

        # 已完成的视频不再累加观看时长
        if not record.is_completed:
            # 有效观看判定：delta 阈值根据倍速动态调整
            # 正常播放 delta ≈ 5 × playback_rate，加 1 秒容差
            max_valid_delta = 5 * playback_rate + 1
            delta = position - record.last_position
            if 0 < delta <= max_valid_delta:
                record.watched_seconds += delta

        # 更新 last_position 和 total_duration
        record.last_position = position
        if total_duration > 0:
            record.total_duration = total_duration

        # 播放到结尾（position 接近总时长）：直接标记 100% 完成
        if total_duration > 0 and position >= total_duration - 2:
            record.watched_seconds = total_duration
            record.is_completed = True

        # 完成判定：有效观看 ≥ 总时长 × 90%
        if not record.is_completed and record.total_duration > 0 and record.watched_seconds >= record.total_duration * 0.9:
            record.is_completed = True

        # 更新时间戳
        record.update_time = int(datetime.now().timestamp())
        record.update_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record.save()

        return get_json_result(data={
            "watched_seconds": record.watched_seconds,
            "is_completed": record.is_completed,
        })
    except Exception as e:
        return get_data_error_result(message=str(e))
