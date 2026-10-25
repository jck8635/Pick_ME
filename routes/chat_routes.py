import logging

from flask import Blueprint, jsonify, render_template, request, session

from services.chat_service import ChatService

logger = logging.getLogger(__name__)

bp = Blueprint("chat", __name__, url_prefix="/chat")

DECISION_PAYLOAD_KEY = "latest_decision_payload"


def _json(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


@bp.route("/")
def index():
    return render_template("chat/index.html")


@bp.route("/api/send", methods=["POST"])
def chat_send():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return _json({
            "status": "error",
            "reply": "요청 형식이 올바르지 않습니다.",
            "parsed_data": None,
            "is_crisis": False,
            "requires_more_info": True,
        }, 400)

    user_message = data.get("message", "")
    tone = data.get("tone", "empathy")

    is_valid, error_message = ChatService.validate_input(user_message)

    if not is_valid:
        return _json({
            "status": "error",
            "reply": error_message,
            "parsed_data": None,
            "is_crisis": False,
            "requires_more_info": True,
        }, 400)

    try:
        ai_result = ChatService.get_ai_response(user_message, tone)
    except Exception:
        logger.exception("chat_send 처리 중 예외 발생")
        return _json({
            "status": "error",
            "reply": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            "parsed_data": None,
            "is_crisis": False,
            "requires_more_info": False,
        }, 500)

    is_crisis = bool(ai_result.get("is_crisis"))
    parsed_data = None if is_crisis else ai_result.get("parsed_data")

    if parsed_data and isinstance(parsed_data, dict):
        # 결정 도우미로 넘길 때 원문 질문·선택지·카테고리를 함께 보관
        payload = {
            "title": parsed_data.get("title") or "",
            "category": parsed_data.get("category") or "기타",
            "options": parsed_data.get("options") or [],
            "content": user_message.strip(),
        }
        session[DECISION_PAYLOAD_KEY] = payload
        parsed_data = payload  # 클라이언트 배너에도 content 포함
    else:
        session.pop(DECISION_PAYLOAD_KEY, None)

    session.modified = True

    return _json({
        "status": "success",
        "reply": ai_result.get("reply", ""),
        "parsed_data": parsed_data,
        "is_crisis": is_crisis,
        "requires_more_info": False,
    })


@bp.route("/api/clear", methods=["POST"])
def chat_clear():
    session.pop("chat_history", None)
    session.pop(DECISION_PAYLOAD_KEY, None)
    session.modified = True

    return _json({
        "status": "success",
        "message": "대화가 초기화되었습니다.",
    })