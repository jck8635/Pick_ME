"""결정 도우미의 비즈니스 로직 담당."""
import os
from google import genai
from google.genai import types

# 개선 1: 고민 카테고리 (복수 선택 가능)
CATEGORIES = [
    "음식/식사", "진로/직업", "소비/쇼핑", "연애/관계",
    "일상/생활", "학습/자기계발", "여행/여가", "기타",
]

# 개선 2: AI 조언 스타일 (상담 중 변경 가능)
STYLES = {
    "soft": "따뜻한 공감형: 친구 같은 어조로 먼저 충분히 공감해주고, 장점 중심으로 부드럽게 조언한다.",
    "objective": "객관적인 분석형: 근거 기반 논리와 데이터처럼 객관적인 시각으로 균형 잡힌 조언을 한다.",
    "fact": "냉정한 팩트형: 우유부단함 없이 현실적이고 냉정하게, 핵심만 간결하게 짚어준다.",
}

# 개선 5: 자주 쓰는 추가 조건 칩 (체크박스)
CONDITION_CHIPS = [
    "예산이 정해져 있음",
    "시간이 급함",
    "식사/일정 후 바로 약속이 있음",
    "주변 사람 의견이 중요",
    "건강/체질을 고려해야 함",
]


# 응답 속도 개선: 가벼운 모델부터 순서대로 시도 (실패 시 다음 모델로 자동 전환)
MODELS = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.0-flash",
]


def get_ai_consultation(prompt: str) -> str:
    """Gemini 모델을 사용하여 AI 상담/결정 도우미 응답을 생성합니다."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "오류: GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요."

    client = genai.Client(api_key=api_key)

    last_error = None
    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=800,  # 속도 개선: 답변 길이 제한
                )
            )
            return response.text
        except Exception as e:
            last_error = e
            continue

    return f"AI 응답 생성 중 오류가 발생했습니다: {str(last_error)}"


def build_prompt(categories, style, title, content, conditions, options=None, criteria=None) -> str:
    """개선 1~5: 카테고리(복수), 스타일, 자유 제목, 가이드 기반 내용, 추가 조건을 반영한 프롬프트."""
    style_guide = STYLES.get(style, STYLES["objective"])
    cat_text = ", ".join(categories) if categories else "지정 없음"

    # 2단계: 비교할 선택지 목록
    opt_lines = ""
    if options:
        opt_lines += "[비교할 선택지]\n"
        for i, opt in enumerate(options, 1):
            line = f"{i}. {opt['title']}"
            if opt.get("note"):
                line += f" - {opt['note']}"
            opt_lines += line + "\n"
        opt_lines += "\n"

    # 3단계: 판단 기준
    crit_text = ", ".join(criteria) if criteria else "지정 없음"

    lines = [
        "당신은 고민 해결을 돕는 상담 전문가입니다. 아래 상담 요청에 답해주세요.",
        "답변은 500자 안내로 간결하게 작성해주세요.",  # 속도 개선
        "",
        f"[고민 카테고리] {cat_text}",
        f"[조언 스타일] {style_guide}",
        f"[고민 제목] {title or '제목 없음'}",
        "",
        "[고민 내용]",
        content,
        "",
        opt_lines or "[비교할 선택지] 없음\n",
        f"[판단 기준] {crit_text}",
        f"[추가 조건 및 특별한 상황] {conditions or '없음'}",
        "",
        "요구사항:",
        "1. 고민 내용을 바탕으로 상황을 짧게 정리해주세요.",
        "2. 선택지가 있다면 선택지별 장단점을 현실적으로 비교해주세요.",
        "3. 판단 기준이 있다면 그 기준 관점에서도 평가해주세요.",
        "4. 지정된 조언 스타일의 말투와 태도를 유지해주세요.",
        "5. 미래나 관계의 결과를 단정하지 말고, 판단 재료를 제시하는 방식으로 조언해주세요.",
        "6. 마지막에 한 줄 추천 결론을 정리해주세요.",
    ]
    return "\n".join(lines)
