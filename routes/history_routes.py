# pickme-flask-main/routes/history_routes.py
from flask import Blueprint, render_template, request, jsonify, session
from services.history_service import HistoryService

bp = Blueprint('history', __name__, url_prefix='/history')

@bp.get('/')
def index():
    return render_template('history/index.html')

# 담당 팀원이 이 파일의 엔드포인트를 구현합니다.

def get_current_user_id():
    """로그인 유저 ID 임시 처리 (회원가입/로그인 파트 연동 전)"""
    return session.get('user_id', 1)

@bp.get('/api/list')
def api_get_history_list():
    """[AJAX] 화면이 열린 후 자바스크립트가 데이터를 요청할 때 응답하는 API"""
    search_query = request.args.get('q', '').strip()
    category = request.args.get('category', '전체')
    bookmarked_only = request.args.get('bookmarked', 'false').lower() == 'true'
    sort_by = request.args.get('sort', 'latest')
    
    histories = HistoryService.get_user_histories(
        get_current_user_id(), search_query, category, bookmarked_only, sort_by
    )
    
    result = []
    for h in histories:
        # result_json에서 옵션/추천 정보를 꺼냄 (없으면 빈 값)
        result_data = h.result_json or {}
        
        result.append({
            "id": h.id,
            "title": h.title,
            "dilemma": h.question,                    # ← question → dilemma로 매핑
            "category": h.category,
            "created_at": h.created_at.strftime('%Y-%m-%d %H:%M') if h.created_at else "",
            "options_data": result_data.get("options", []),           # 필요시 사용
            "recommendation_data": result_data.get("result"),   # ← recommendation → result 로 변경
            "is_bookmarked": h.is_bookmarked,
            "actual_choice": h.actual_choice,
            "satisfaction_score": h.satisfaction_score,
            "retrospective_note": h.retrospective_note
        })
    return jsonify(result)

@bp.post('/api/<decision_id>/bookmark')
def api_toggle_bookmark(decision_id):
    """[AJAX] 북마크 토글"""
    try:
        decision_id = int(decision_id)  # ← 이 한 줄 추가
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "잘못된 ID입니다."}), 400

    new_status = HistoryService.toggle_bookmark(decision_id, get_current_user_id())
    if new_status is not None:
        return jsonify({"success": True, "is_bookmarked": new_status})
    return jsonify({"success": False, "error": "찾을 수 없습니다."}), 404

@bp.post('/api/<decision_id>/retrospective')
def api_update_retrospective(decision_id):
    """[AJAX] 회고 내용 업데이트"""
    try:
        decision_id = int(decision_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "잘못된 ID입니다."}), 400

    data = request.get_json() or {}
    
    try:
        success = HistoryService.update_retrospective(
            decision_id, 
            get_current_user_id(),
            data.get('actualChoice'),
            data.get('satisfactionScore'),
            data.get('retrospectiveNote')
        )
        return jsonify({"success": success})
    except ValueError as e:
        # 만족도 점수 형식 오류 등
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        # 기타 예외
        return jsonify({"success": False, "error": "서버 오류가 발생했습니다."}), 500

@bp.delete('/api/<decision_id>')
def api_delete_history(decision_id):
    """[AJAX] 단건 삭제"""
    try:
        decision_id = int(decision_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "잘못된 ID입니다."}), 400

    if HistoryService.delete_history(decision_id, get_current_user_id()):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "찾을 수 없습니다."}), 404
    

@bp.delete('/api/clear')
def api_clear_history():
    """[AJAX] 전체 기록 삭제"""
    HistoryService.clear_all_history(get_current_user_id())
    return jsonify({"success": True})
