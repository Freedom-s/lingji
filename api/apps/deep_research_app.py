import json
import logging

import httpx
from flask import Blueprint, Response, request
from flask_login import login_required

from api.utils.api_utils import server_error_response, validate_request

logger = logging.getLogger(__name__)

DEEPER_FLOW_URL = "http://localhost:8001/api/chat/stream"
TIMEOUT_SECONDS = 600.0

manager = Blueprint("deep_research", __name__)


def _transform_event(event_type, data):
    """Transform DeerFlow SSE event to RAGFlow format.

    DeerFlow SSE:  event: <type>\\ndata: <json>\\n\\n
    RAGFlow SSE:   data: {"code":0, "message":"", "data": {...}}\\n\\n
    """
    if event_type is None:
        return None

    if event_type == "message_chunk":
        return {
            "code": 0,
            "message": "",
            "data": {
                "event": "message_chunk",
                "agent": data.get("agent", "unknown"),
                "content": data.get("content", ""),
                "thread_id": data.get("thread_id"),
                "finish_reason": data.get("finish_reason"),
            },
        }

    elif event_type == "tool_calls":
        return {
            "code": 0,
            "message": "",
            "data": {
                "event": "tool_calls",
                "agent": data.get("agent", "unknown"),
                "content": data.get("content", ""),
                "tool_calls": data.get("tool_calls", []),
            },
        }

    elif event_type == "tool_call_chunks":
        return {
            "code": 0,
            "message": "",
            "data": {
                "event": "tool_call_chunks",
                "agent": data.get("agent", "unknown"),
                "tool_call_chunks": data.get("tool_call_chunks", []),
            },
        }

    elif event_type == "tool_call_result":
        return {
            "code": 0,
            "message": "",
            "data": {
                "event": "tool_call_result",
                "agent": data.get("agent", "unknown"),
                "content": data.get("content", ""),
                "tool_call_id": data.get("tool_call_id"),
            },
        }

    elif event_type == "interrupt":
        return {
            "code": 0,
            "message": "",
            "data": {
                "event": "interrupt",
                "content": data.get("content", ""),
                "options": data.get("options", []),
            },
        }

    elif event_type == "citations":
        return {
            "code": 0,
            "message": "",
            "data": {
                "event": "citations",
                "citations": data.get("citations", []),
            },
        }

    elif event_type == "error":
        return {
            "code": 500,
            "message": data.get("error", "Unknown error"),
            "data": {
                "event": "error",
                "error": data.get("error", ""),
                "reason": data.get("reason", ""),
            },
        }

    return None


@manager.route("/completion", methods=["POST"])
@login_required
@validate_request("messages")
def completion():
    req = request.json
    messages = req.get("messages", [])

    report_style = req.get("report_style", "academic")
    locale = req.get("locale", "zh-CN")
    max_plan_iterations = req.get("max_plan_iterations", 1)
    max_step_num = req.get("max_step_num", 3)
    enable_web_search = req.get("enable_web_search", True)
    auto_accepted_plan = req.get("auto_accepted_plan", True)
    enable_background_investigation = req.get(
        "enable_background_investigation", True
    )

    deerflow_body = {
        "messages": [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in messages
        ],
        "report_style": report_style,
        "locale": locale,
        "max_plan_iterations": max_plan_iterations,
        "max_step_num": max_step_num,
        "enable_web_search": enable_web_search,
        "auto_accepted_plan": auto_accepted_plan,
        "enable_background_investigation": enable_background_investigation,
    }

    def stream():
        try:
            with httpx.stream(
                "POST", DEEPER_FLOW_URL, json=deerflow_body, timeout=TIMEOUT_SECONDS
            ) as response:
                if response.status_code != 200:
                    yield "data:" + json.dumps(
                        {
                            "code": 500,
                            "message": f"DeerFlow returned {response.status_code}",
                            "data": {
                                "answer": f"**ERROR**: DeerFlow service error ({response.status_code})",
                                "reference": {},
                            },
                        },
                        ensure_ascii=False,
                    ) + "\n\n"
                    yield "data:" + json.dumps(
                        {"code": 0, "message": "", "data": True}, ensure_ascii=False
                    ) + "\n\n"
                    return

                current_event_type = None
                for line in response.iter_lines():
                    if line.startswith("event: "):
                        current_event_type = line[7:].strip()
                    elif line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        wrapped = _transform_event(current_event_type, data)
                        if wrapped is not None:
                            yield "data:" + json.dumps(
                                wrapped, ensure_ascii=False
                            ) + "\n\n"

        except httpx.ConnectError:
            logger.error("Cannot connect to DeerFlow on port 8001")
            yield "data:" + json.dumps(
                {
                    "code": 500,
                    "message": "Cannot connect to DeerFlow service",
                    "data": {
                        "answer": "**ERROR**: 无法连接到深度研究服务，请确认 DeerFlow 已在端口 8001 上启动。",
                        "reference": {},
                    },
                },
                ensure_ascii=False,
            ) + "\n\n"
        except httpx.ReadTimeout:
            logger.error("DeerFlow request timed out")
            yield "data:" + json.dumps(
                {
                    "code": 500,
                    "message": "DeerFlow request timed out",
                    "data": {
                        "answer": "**ERROR**: 深度研究请求超时。",
                        "reference": {},
                    },
                },
                ensure_ascii=False,
            ) + "\n\n"
        except Exception as e:
            logger.exception("Error proxying DeerFlow stream")
            yield "data:" + json.dumps(
                {
                    "code": 500,
                    "message": str(e),
                    "data": {
                        "answer": f"**ERROR**: {str(e)}",
                        "reference": {},
                    },
                },
                ensure_ascii=False,
            ) + "\n\n"
        finally:
            yield "data:" + json.dumps(
                {"code": 0, "message": "", "data": True}, ensure_ascii=False
            ) + "\n\n"

    resp = Response(stream(), mimetype="text/event-stream")
    resp.headers.add_header("Cache-control", "no-cache")
    resp.headers.add_header("Connection", "keep-alive")
    resp.headers.add_header("X-Accel-Buffering", "no")
    resp.headers.add_header("Content-Type", "text/event-stream; charset=utf-8")
    return resp
