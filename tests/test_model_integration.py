r"""실제 SQLAlchemy 매퍼/DDL의 오프라인 검증. DB 연결과 테이블 생성은 차단한다.

프로젝트 루트에서 실행:
  .venv\Scripts\python.exe -B -m unittest tests.test_db_setup tests.test_model_integration -v
"""

import secrets
import unittest
import warnings
from unittest.mock import patch

from sqlalchemy import CheckConstraint, Integer, UniqueConstraint, func, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable
from werkzeug.security import check_password_hash

from extensions import db
from models import Comment, CommunityLike, CommunityVote, Decision, Post, PostOption, User
from services import member_service


MODELS = {
    'user': User,
    'decision': Decision,
    'post': Post,
    'comment': Comment,
    'post_options': PostOption,
    'community_votes': CommunityVote,
    'community_likes': CommunityLike,
}


class ModelIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.enterClassContext(patch.object(Engine, 'connect', side_effect=AssertionError('DB access forbidden')))
        cls.enterClassContext(patch.object(db, 'create_all', side_effect=AssertionError('DDL execution forbidden')))
        with warnings.catch_warnings():
            warnings.simplefilter('error', SAWarning)
            configure_mappers()

    def test_registered_tables_and_integer_primary_keys(self):
        self.assertEqual(set(db.metadata.tables), set(MODELS))
        for table_name, model in MODELS.items():
            with self.subTest(table=table_name):
                table = inspect(model).local_table
                self.assertEqual(table.name, table_name)
                self.assertEqual([col.name for col in table.primary_key], ['id'])
                self.assertIsInstance(table.c.id.type, Integer)

    def test_all_foreign_keys_resolve_to_existing_integer_primary_keys(self):
        expected = {
            'decision.user_id': 'user.id',
            'post.user_id': 'user.id',
            'comment.post_id': 'post.id',
            'comment.user_id': 'user.id',
            'post_options.post_id': 'post.id',
            'community_votes.post_id': 'post.id',
            'community_votes.option_id': 'post_options.id',
            'community_votes.user_id': 'user.id',
            'community_likes.post_id': 'post.id',
            'community_likes.user_id': 'user.id',
        }
        actual = {}
        for table in db.metadata.tables.values():
            for fk in table.foreign_keys:
                actual[f'{table.name}.{fk.parent.name}'] = fk.target_fullname
                self.assertIsInstance(fk.parent.type, Integer)
                self.assertIsInstance(fk.column.type, Integer)
                self.assertTrue(fk.column.primary_key)
                self.assertFalse(fk.parent.nullable)
        self.assertEqual(actual, expected)
        vote_option_fk = next(iter(CommunityVote.__table__.c.option_id.foreign_keys))
        self.assertEqual(vote_option_fk.ondelete, 'CASCADE')

    def test_unique_constraints_keep_member_and_community_contracts(self):
        def uniques(model):
            return {tuple(col.name for col in constraint.columns)
                    for constraint in model.__table__.constraints if isinstance(constraint, UniqueConstraint)}
        self.assertEqual(uniques(User), {('email',), ('nickname',)})
        for model in (CommunityVote, CommunityLike):
            self.assertEqual(uniques(model), {('post_id', 'user_id')})

    def test_decision_additions_keep_question_and_json(self):
        columns = Decision.__table__.c
        self.assertTrue({'question', 'result_json', 'category', 'is_bookmarked', 'actual_choice',
                         'satisfaction_score', 'retrospective_note'}.issubset(columns.keys()))
        self.assertFalse(columns.question.nullable)
        self.assertTrue(columns.result_json.nullable)
        self.assertTrue(columns.satisfaction_score.nullable)
        self.assertIsInstance(columns.satisfaction_score.type, Integer)
        self.assertFalse(columns.is_bookmarked.nullable)
        self.assertIs(columns.is_bookmarked.default.arg, False)
        self.assertIsNotNone(columns.is_bookmarked.server_default)

    def test_satisfaction_check_compiles_for_postgresql(self):
        constraints = [constraint for constraint in Decision.__table__.constraints
                       if isinstance(constraint, CheckConstraint)]
        self.assertEqual(len(constraints), 1)
        ddl = str(CreateTable(Decision.__table__).compile(dialect=postgresql.dialect()))
        self.assertIn('satisfaction_score IS NULL OR satisfaction_score BETWEEN 1 AND 5', ddl)
        self.assertIn('BOOLEAN DEFAULT false NOT NULL', ddl)

    def test_community_column_names_and_defaults_match_service(self):
        name = PostOption.__table__.c.name
        self.assertEqual(name.type.length, 120)
        self.assertFalse(name.nullable)
        self.assertNotIn('content', PostOption.__table__.c)
        self.assertEqual(Post.__table__.c.category.type.length, 40)
        self.assertEqual(Post.__table__.c.category.default.arg, '기타')
        for model in (Post, Comment, CommunityVote, CommunityLike):
            self.assertIn('created_at', model.__table__.c)
            self.assertTrue(model.__table__.c.created_at.type.timezone)
        self.assertIsNotNone(Post.__table__.c.updated_at.onupdate)

    def test_post_relationships_and_reverse_sides(self):
        expected = {'options': (PostOption, 'options'), 'comments': (Comment, 'comments'),
                    'likes': (CommunityLike, 'likes'), 'votes': (CommunityVote, 'votes')}
        for name, (child, reverse) in expected.items():
            with self.subTest(relationship=name):
                relationship = inspect(Post).relationships[name]
                self.assertIs(relationship.mapper.class_, child)
                self.assertTrue(relationship.uselist)
                self.assertEqual(relationship.back_populates, 'post')
                self.assertEqual(inspect(child).relationships.post.back_populates, reverse)
                self.assertIn('delete-orphan', relationship.cascade)
        for model in (Post, Comment):
            self.assertIs(inspect(model).relationships.author.mapper.class_, User)

    def test_vote_option_relationship_and_collection_synchronization(self):
        post = Post(user_id=1, title='Choice', content='Question', category='기타')
        option = PostOption(name='First')
        post.options = [option]
        vote = CommunityVote(user_id=2)
        post.votes.append(vote)
        option.votes.append(vote)
        self.assertIs(option.post, post)
        self.assertIs(vote.post, post)
        self.assertIs(vote.option, option)
        self.assertEqual(inspect(CommunityVote).relationships.option.back_populates, 'votes')
        self.assertEqual(inspect(PostOption).relationships.votes.back_populates, 'option')

    def test_all_tables_compile_to_postgresql_ddl_without_execution(self):
        for table in db.metadata.sorted_tables:
            with self.subTest(table=table.name):
                ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
                self.assertIn('CREATE TABLE', ddl)
                self.assertNotIn('DROP TABLE', ddl)

    def test_community_search_and_vote_count_expressions_compile(self):
        search = select(Post).where(Post.options.any(PostOption.name.ilike('%example%')))
        compiled = str(search.compile(dialect=postgresql.dialect()))
        self.assertIn('EXISTS', compiled)
        self.assertIn('post_options.name ILIKE', compiled)
        self.assertIn('post.id = post_options.post_id', compiled)
        counts = select(CommunityVote.option_id, func.count(CommunityVote.id)).group_by(CommunityVote.option_id)
        self.assertIn('GROUP BY community_votes.option_id', str(counts.compile(dialect=postgresql.dialect())))

    def test_member_registration_login_and_profile_service_compatibility(self):
        # 실제 암호화 함수를 사용하지만 저장/조회/commit은 모의 세션만 사용한다.
        initial = secrets.token_urlsafe(16)
        replacement = secrets.token_urlsafe(16)
        with patch.object(db, 'session') as session:
            session.scalar.return_value = None
            user = member_service.register_member('Member@Example.com', 'member', initial)
            self.assertEqual(user.email, 'member@example.com')
            self.assertTrue(check_password_hash(user.password_hash, initial))
            session.scalar.return_value = user
            self.assertIs(member_service.authenticate_member(user.email, initial), user)
            with self.assertRaises(member_service.MemberError):
                member_service.authenticate_member(user.email, replacement)
            session.scalar.return_value = None
            member_service.change_nickname(user, 'updated-member')
            self.assertEqual(user.nickname, 'updated-member')
            member_service.change_password(user, initial, replacement, replacement)
            self.assertTrue(check_password_hash(user.password_hash, replacement))
            self.assertFalse(check_password_hash(user.password_hash, initial))
            self.assertEqual(session.commit.call_count, 3)


if __name__ == '__main__':
    unittest.main()
