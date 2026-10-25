"""결정 도우미 라우트. 개선 1~7 반영."""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session

from models.entities import Decision, db
from services.decision_service import (
    get_ai_consultation, build_prompt, CATEGORIES, STYLES, CONDITION_CHIPS,
)

bp = Blueprint('decision', __name__, url_prefix='/decision')


@bp.route('/', methods=['GET', 'POST'])
def index():
    """개선 3: 자유로운 고민 제목 + 개선 4: 가이드 기반 입력으로 상담 요청을 받는다."""
    ai_result = None
    error = None

    if request.method == 'POST':
        # 개선 1: 카테고리 복수 선택
        categories = request.form.getlist('categories')
        style = request.form.get('style', 'objective')
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        # 개선 5: 칩(체크박스) + 자유 입력 조건을 모두 반영
        chips = request.form.getlist('conditions')
        free_text = request.form.get('conditions_free', '').strip()
        conditions = ", ".join(chips + ([free_text] if free_text else []))

        # 2단계: 비교할 선택지 (같은 페이지에서 함께 제출됨)
        opt_titles = request.form.getlist('option_title')
        opt_notes = request.form.getlist('option_note')
        options = [
            {"title": t.strip(), "note": n.strip()}
            for t, n in zip(opt_titles, opt_notes) if t.strip()
        ]

        # 3단계: 판단 기준 + 기준별 가중치 (JS가 "weight_<기준명>" 이름으로 1~5점을 보낸다)
        criteria = request.form.getlist('criteria')
        weights = {k[len('weight_'):]: v for k, v in request.form.items()
                   if k.startswith('weight_')}
        crit_text = ", ".join(f"{c}({weights.get(c, '?')}점)" for c in criteria) \
            if criteria else "지정 없음"

        if not content:
            error = "고민 내용을 입력해 주세요."
        else:
            # ★ 한 페이지 방식: 1~3단계 값을 모아 바로 AI 상담 실행
            options_full = [
                {"title": o["title"], "note": o["note"]} for o in options
            ]
            prompt = build_prompt(categories, style, title, content, conditions,
                                  options=options_full, criteria=crit_text)
            ai_result = get_ai_consultation(prompt)

            # 상담 기록 저장 (로그인한 사용자만)
            if ai_result and not ai_result.startswith(("오류", "AI 응답")):
                if 'user_id' in session:
                    try:
                        record = Decision(
                            user_id=session['user_id'],
                            title=title or content[:50],
                            question=content,
                            result_json={
                                "categories": categories, "style": style,
                                "conditions": conditions,
                                "options": options_full, "criteria": crit_text,
                                "result": ai_result,
                            },
                        )
                        db.session.add(record)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

            session.pop('latest_decision_payload', None)
            return render_template(
                'decision/index.html',
                result=ai_result, error=None,
                categories=CATEGORIES, styles=STYLES, chips=CONDITION_CHIPS,
                form=request.form,
                prefill_options=_prefill_options_list(request.form),
                from_chat=False,
            )

    # GET: AI 상담에서 넘어온 선택지/제목/내용 미리 채우기
    prefill = _build_prefill_form()
    form = request.form if request.method == 'POST' else prefill

    return render_template(
        'decision/index.html',
        result=ai_result, error=error,
        categories=CATEGORIES, styles=STYLES, chips=CONDITION_CHIPS,
        # ★ 입력 리셋 방지: 제출한 값 그대로 돌려보내 화면에 유지
        form=form,
        prefill_options=_prefill_options_list(form),
        from_chat=bool(session.get('latest_decision_payload')),
    )


# AI 상담 → 결정 도우미 카테고리 이름 맞추기
_CATEGORY_MAP = {
    "진로/이직": "진로/직업",
    "쇼핑/소비": "소비/쇼핑",
    "진로/직업": "진로/직업",
    "소비/쇼핑": "소비/쇼핑",
    "음식/식사": "음식/식사",
    "학습/자기계발": "학습/자기계발",
    "여행/여가": "여행/여가",
    "연애/관계": "연애/관계",
    "일상/생활": "일상/생활",
    "기타": "기타",
}


def _prefill_options_list(form):
    """폼에서 선택지 목록을 꺼내 템플릿에 넘긴다."""
    titles = form.getlist('option_title') if hasattr(form, 'getlist') else []
    notes = form.getlist('option_note') if hasattr(form, 'getlist') else []
    options = []
    for i, t in enumerate(titles):
        t = (t or '').strip()
        if not t:
            continue
        n = notes[i] if i < len(notes) else ''
        options.append({"title": t, "note": (n or '').strip()})
    while len(options) < 2:
        options.append({"title": "", "note": ""})
    return options[:5]


def _build_prefill_form():
    """세션(AI 상담) 또는 쿼리스트링으로 넘어온 값을 MultiDict 형태로 만든다."""
    from werkzeug.datastructures import MultiDict

    data = []
    payload = session.get('latest_decision_payload') or {}

    # 쿼리스트링 우선(직접 링크), 없으면 세션
    q_title = (request.args.get('title') or '').strip()
    q_category = (request.args.get('category') or '').strip()
    q_content = (request.args.get('content') or '').strip()
    q_options = request.args.get('options')  # JSON 배열 문자열

    title = q_title or (payload.get('title') or '').strip()
    category = q_category or (payload.get('category') or '').strip()
    content = q_content or (payload.get('content') or '').strip()

    options = []
    if q_options:
        import json
        try:
            raw = json.loads(q_options)
            if isinstance(raw, list):
                options = [str(x).strip() for x in raw if str(x).strip()]
        except Exception:
            options = []
    if not options:
        raw_opts = payload.get('options') or []
        if isinstance(raw_opts, list):
            options = [str(x).strip() for x in raw_opts if str(x).strip()]

    if title:
        data.append(('title', title))
    if content:
        data.append(('content', content))

    mapped = _CATEGORY_MAP.get(category, category)
    if mapped in CATEGORIES:
        data.append(('categories', mapped))

    for opt in options[:5]:
        data.append(('option_title', opt))
        data.append(('option_note', ''))

    # 한 번 쓰면 세션에서 제거하지 않음 — 사용자가 수정·재제출할 수 있게 유지
    # (초기화는 채팅 clear 또는 결정 제출 성공 시에만)
    return MultiDict(data)


# 2단계(비교할 선택지 작성) 화면
@bp.route('/new', methods=['GET'])
def new():
    draft = session.get('decision_draft', {})
    # AI 상담에서 넘어온 선택지 우선
    payload = session.get('latest_decision_payload') or {}
    options = []
    raw_opts = payload.get('options') or []
    if isinstance(raw_opts, list):
        for o in raw_opts[:5]:
            if str(o).strip():
                options.append({"title": str(o).strip(), "note": ""})
    # 쿼리 options
    q_options = request.args.get('options')
    if q_options and not options:
        import json
        try:
            raw = json.loads(q_options)
            if isinstance(raw, list):
                options = [{"title": str(x).strip(), "note": ""} for x in raw if str(x).strip()]
        except Exception:
            pass
    if len(options) < 2:
        options = options + [{"title": "", "note": ""}] * (2 - len(options))
    return render_template('decision/new.html', options=options[:5], draft=draft)


# 2단계 제출 → 3단계(판단 기준 + 가중치)로 이동
@bp.route('/new/submit', methods=['POST'])
def new_submit():
    draft = session.get('decision_draft')
    if not draft:
        return redirect(url_for('decision.index'))

    opt_titles = request.form.getlist('option_title')
    opt_notes = request.form.getlist('option_note')
    options = [
        {"title": t.strip(), "note": n.strip()}
        for t, n in zip(opt_titles, opt_notes) if t.strip()
    ]
    session['decision_options'] = [
        {"title": o["title"], "note": o["note"]} for o in options
    ]
    return redirect(url_for('decision.conditions'))


# 3단계(판단 기준 + 가중치) 화면
@bp.route('/conditions', methods=['GET'])
def conditions():
    draft = session.get('decision_draft')
    if not draft:
        return redirect(url_for('decision.index'))
    options = session.get('decision_options', [])
    return render_template(
        'decision/conditions.html',
        options=options, draft=draft,
        form={**draft, 'option_title': [o['title'] for o in options],
              'option_note': [o['note'] for o in options]},
    )


def session_guard():
    from flask import session
    return session


# 3단계 제출 → 가중치를 반영한 AI 상담 실행
@bp.route('/conditions/submit', methods=['POST'])
def conditions_submit():
    draft = session.get('decision_draft')
    if not draft:
        return redirect(url_for('decision.index'))

    options = session.get('decision_options', [])
    criteria = request.form.getlist('criteria')   # 체크한 판단 기준

    # 브라우저 JS가 "weight_<기준명>" 이름으로 1~5점을 보낸다 → 기준별 가중치로 정리
    weights = {}
    for key, val in request.form.items():
        if key.startswith('weight_'):
            crit = key[len('weight_'):]
            weights[crit] = val

    # 가중치를 "기준명(가중치)" 형태로 정리해 AI에게 전달
    crit_text = ", ".join(
        f"{c}({weights.get(c, '?')}점)" for c in criteria
    ) if criteria else "지정 없음"

    categories = draft.get('categories', [])
    style = draft.get('style', 'objective')
    title = draft.get('title', '')
    content = draft.get('content', '')
    conditions = ", ".join(
        draft.get('conditions', []) +
        ([draft['conditions_free']] if draft.get('conditions_free') else [])
    )

    if not content:
        return render_template('decision/conditions.html', options=options,
                               error="고민 내용이 비어 있어요. 1단계부터 다시 입력해 주세요.")

    prompt = build_prompt(categories, style, title, content, conditions,
                          options=options, criteria=crit_text)
    ai_result = get_ai_consultation(prompt)

    # 상담 기록 저장 (로그인한 사용자만)
    if ai_result and not ai_result.startswith(("오류", "AI 응답")):
        if 'user_id' in session:
            try:
                record = Decision(
                    user_id=session['user_id'],
                    title=title or content[:50],
                    question=content,
                    result_json={
                        "categories": categories, "style": style,
                        "conditions": conditions,
                        "options": options, "criteria": crit_text,
                        "result": ai_result,
                    },
                )
                db.session.add(record)
                db.session.commit()
            except Exception:
                db.session.rollback()

    # 상담 끝나면 세션 정리
    form = {**draft, 'option_title': [o['title'] for o in options],
            'option_note': [o['note'] for o in options]}
    session.pop('decision_draft', None)
    session.pop('decision_options', None)

    return render_template(
        'decision/conditions.html',
        options=options, result=ai_result, error=None,
        submitted_criteria=criteria, weights=weights,
        form=form,
    )

# 개선 1: 카테고리별 인기 고민 Top 5 조회 API
@bp.get('/api/popular')
def api_popular():
    from sqlalchemy import func
    q = (
        db.session.query(Decision.title, func.count(Decision.id).label('cnt'))
        .group_by(Decision.title)
        .order_by(func.count(Decision.id).desc())
        .limit(5)
        .all()
    )
    return jsonify([{"title": t, "count": c} for t, c in q])


# 개선 2: 상담 결과 화면에서 스타일만 바꿔 다시 상담 (예: "공감은 됐고, 이제 팩트로 말해줘")
@bp.post('/api/restyle')
def api_restyle():
    data = request.get_json(silent=True) or {}
    style = data.get('style', 'fact')
    categories = data.get('categories', [])
    title = data.get('title', '')
    content = data.get('content', '')
    conditions = data.get('conditions', '')

    if not content:
        return jsonify({"error": "고민 내용이 없습니다."}), 400

    prompt = build_prompt(categories, style, title, content, conditions)
    return jsonify({"result": get_ai_consultation(prompt)})
