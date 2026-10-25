"""고민 기록의 비즈니스 로직 담당. 팀원 구현 영역."""

from models.entities import Decision
from extensions import db
from sqlalchemy import or_, desc, asc


class HistoryService:
    @staticmethod
    def get_user_histories(user_id, search_query='', category='전체', bookmarked_only=False, sort_by='latest'):
        """조건에 맞는 유저의 고민 기록 목록을 조회합니다."""
        query = Decision.query.filter_by(user_id=user_id)

        # 1. 카테고리 필터
        if category and category != '전체':
            query = query.filter_by(category=category)

        # 2. 북마크 필터
        if bookmarked_only:
            query = query.filter_by(is_bookmarked=True)

        # 3. 키워드 검색 (제목, 질문 내용에서 검색)
        if search_query:
            query = query.filter(or_(
                Decision.title.ilike(f'%{search_query}%'),
                Decision.question.ilike(f'%{search_query}%')  # dilemma → question
            ))

        # 4. 정렬
        if sort_by == 'oldest':
            query = query.order_by(asc(Decision.created_at))
        else:
            # 기본값: 북마크 우선 + 최신순
            query = query.order_by(desc(Decision.is_bookmarked), desc(Decision.created_at))

        return query.all()

    @staticmethod
    def toggle_bookmark(decision_id, user_id):
        """특정 기록의 북마크 상태를 반전시킵니다."""
        decision = Decision.query.filter_by(id=decision_id, user_id=user_id).first()
        if decision:
            decision.is_bookmarked = not decision.is_bookmarked
            db.session.commit()
            return decision.is_bookmarked
        return None

    @staticmethod
    def update_retrospective(decision_id, user_id, actual_choice, satisfaction_score, retrospective_note):
        """회고 내용 업데이트"""
        
        if satisfaction_score is not None and satisfaction_score != '':
            # 1. 먼저 정수 변환이 가능한지 확인
            try:
                satisfaction_score = int(satisfaction_score)
            except (ValueError, TypeError):
                raise ValueError("잘못된 만족도 점수 형식입니다.")
            
            # 2. 변환된 정수가 1~5 사이인지 확인 (try-except 밖으로 빼기)
            if not (1 <= satisfaction_score <= 5):
                raise ValueError("만족도 점수는 1점에서 5점 사이여야 합니다.")
        else:
            satisfaction_score = None  

        decision = Decision.query.filter_by(id=decision_id, user_id=user_id).first()
        if not decision:
            return False
            
        decision.actual_choice = actual_choice
        decision.satisfaction_score = satisfaction_score
        decision.retrospective_note = retrospective_note
        db.session.commit()
        return True

    @staticmethod
    def delete_history(decision_id, user_id):
        """특정 기록을 삭제합니다."""
        decision = Decision.query.filter_by(id=decision_id, user_id=user_id).first()
        if decision:
            db.session.delete(decision)
            db.session.commit()
            return True
        return False

    @staticmethod
    def clear_all_history(user_id):
        """유저의 모든 고민 기록을 삭제합니다."""
        Decision.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return True