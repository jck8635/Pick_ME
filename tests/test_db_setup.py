"""오프라인 DB 준비 회귀 테스트. Flask import, DB 접속, 실제 DDL을 수행하지 않는다.

실행: python -m unittest tests.test_db_setup -v
연결 확인은 별도로 python init_db.py --check 를 사용한다.
"""

import ast
import contextlib
import io
import secrets
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import init_db

ROOT = Path(__file__).resolve().parents[1]


def fake_runtime():
    """DB에 접근할 수 없는 모의 객체만 생성한다."""
    app = MagicMock()
    db = MagicMock()
    db.engine.url = SimpleNamespace(drivername='postgresql+psycopg', database='neondb')
    pairs = [('User', 'user'), ('Decision', 'decision'), ('Post', 'post'), ('Comment', 'comment'),
             ('PostOption', 'post_options'), ('CommunityVote', 'community_votes'),
             ('CommunityLike', 'community_likes')]
    db.Model.registry.mappers = [
        SimpleNamespace(class_=SimpleNamespace(__name__=model), local_table=SimpleNamespace(fullname=table))
        for model, table in pairs
    ]
    db.metadata.sorted_tables = [SimpleNamespace(fullname=table) for _, table in pairs]
    connection = db.engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    connection.exec_driver_sql.return_value.one.return_value = SimpleNamespace(
        connected=1, database_name='neondb', transaction_read_only='on')
    return app, db, connection


class DbCommandTests(unittest.TestCase):
    def setUp(self):
        self.app, self.db, self.connection = fake_runtime()
        self.stdout, self.stderr = io.StringIO(), io.StringIO()
        self.loader = self.enterContext(patch.object(init_db, '_load_runtime', return_value=(self.app, self.db)))
        self.enterContext(contextlib.redirect_stdout(self.stdout))
        self.enterContext(contextlib.redirect_stderr(self.stderr))

    def test_default_and_preview_do_not_connect_or_create(self):
        for argv in ([], ['--preview']):
            with self.subTest(argv=argv):
                self.assertEqual(init_db.main(argv), 0)
        self.db.engine.connect.assert_not_called()
        self.db.create_all.assert_not_called()
        for name in ('User', 'Decision', 'Post', 'Comment', 'PostOption', 'CommunityVote', 'CommunityLike',
                     'user', 'decision', 'post', 'comment', 'post_options', 'community_votes', 'community_likes'):
            self.assertIn(name, self.stdout.getvalue())

    def test_create_requires_pm_approval_before_runtime_is_loaded(self):
        with self.assertRaises(SystemExit) as result:
            init_db.main(['--create'])
        self.assertEqual(result.exception.code, 2)
        self.loader.assert_not_called()
        self.db.create_all.assert_not_called()

    def test_approval_without_create_is_rejected(self):
        with self.assertRaises(SystemExit) as result:
            init_db.main(['--check', '--pm-approved'])
        self.assertEqual(result.exception.code, 2)
        self.loader.assert_not_called()

    def test_check_and_create_cannot_be_combined(self):
        with self.assertRaises(SystemExit) as result:
            init_db.main(['--check', '--create', '--pm-approved'])
        self.assertEqual(result.exception.code, 2)
        self.loader.assert_not_called()

    def test_approved_create_prints_inventory_before_mocked_creation(self):
        def check_inventory():
            for name in ('User', 'Decision', 'Post', 'Comment'):
                self.assertIn(name, self.stdout.getvalue())
        self.db.create_all.side_effect = check_inventory
        self.assertEqual(init_db.main(['--create', '--pm-approved']), 0)
        self.db.create_all.assert_called_once_with()
        self.db.drop_all.assert_not_called()

    def test_wrong_driver_and_database_never_connect_or_create(self):
        for driver, database in [('sqlite', 'neondb'), ('postgresql+psycopg2', 'neondb'), ('postgresql+psycopg', 'other')]:
            with self.subTest(driver=driver, database=database):
                self.db.engine.url = SimpleNamespace(drivername=driver, database=database)
                self.assertEqual(init_db.main(['--create', '--pm-approved']), 1)
        self.db.engine.connect.assert_not_called()
        self.db.create_all.assert_not_called()

    def test_check_uses_read_only_transaction_and_only_select(self):
        self.assertEqual(init_db.main(['--check']), 0)
        self.connection.execution_options.assert_called_once_with(postgresql_readonly=True)
        self.connection.begin.assert_called_once_with()
        self.connection.exec_driver_sql.assert_called_once()
        sql = self.connection.exec_driver_sql.call_args.args[0]
        self.assertTrue(sql.startswith('SELECT '))
        self.assertNotIn('FROM ', sql.upper())
        self.db.create_all.assert_not_called()

    def test_check_rejects_non_read_only_or_wrong_database(self):
        for readonly, database in [('off', 'neondb'), ('on', 'other')]:
            with self.subTest(readonly=readonly, database=database):
                self.connection.exec_driver_sql.return_value.one.return_value = SimpleNamespace(
                    connected=1, database_name=database, transaction_read_only=readonly)
                self.assertEqual(init_db.main(['--check']), 1)
        self.db.create_all.assert_not_called()

    def test_connection_exception_details_are_not_printed(self):
        opaque_detail = secrets.token_urlsafe(24)
        self.db.engine.connect.side_effect = RuntimeError(opaque_detail)
        self.assertEqual(init_db.main(['--check']), 1)
        self.assertNotIn(opaque_detail, self.stdout.getvalue() + self.stderr.getvalue())
        self.db.create_all.assert_not_called()

    def test_creation_exception_details_are_not_printed(self):
        opaque_detail = secrets.token_urlsafe(24)
        self.db.create_all.side_effect = RuntimeError(opaque_detail)
        self.assertEqual(init_db.main(['--create', '--pm-approved']), 1)
        self.assertNotIn(opaque_detail, self.stdout.getvalue() + self.stderr.getvalue())

    def test_missing_dependencies_return_a_safe_error(self):
        self.loader.side_effect = ModuleNotFoundError()
        self.assertEqual(init_db.main([]), 1)
        self.db.create_all.assert_not_called()


class SharedSchemaTests(unittest.TestCase):
    def test_app_has_no_automatic_schema_creation_or_deletion(self):
        tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8-sig'))
        schema_calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and node.func.attr in {'create_all', 'drop_all'}]
        self.assertEqual(schema_calls, [])
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == 'create_app' for node in tree.body))

    def test_shared_model_columns_and_foreign_keys_are_preserved(self):
        tree = ast.parse((ROOT / 'models/entities.py').read_text(encoding='utf-8-sig'))
        expected_columns = {
            'User': ['id', 'email', 'password_hash', 'nickname'],
            'Decision': ['id', 'user_id', 'title', 'question', 'result_json', 'created_at'],
            'Post': ['id', 'user_id', 'title', 'content', 'created_at'],
            'Comment': ['id', 'post_id', 'user_id', 'content'],
        }
        expected_fks = {'Decision': ['user.id'], 'Post': ['user.id'], 'Comment': ['post.id', 'user.id'], 'User': []}
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertTrue(set(expected_columns).issubset(classes))
        for name in expected_columns:
            model = classes[name]
            with self.subTest(model=name):
                columns = [node for node in model.body if isinstance(node, ast.Assign)
                           and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                           and node.value.func.attr == 'Column']
                # Additive integration may add columns, but cannot remove/rename the old ones.
                self.assertEqual([node.targets[0].id for node in columns
                                  if node.targets[0].id in expected_columns[name]], expected_columns[name])
                table_names = [node.value.value for node in model.body if isinstance(node, ast.Assign)
                               and any(isinstance(t, ast.Name) and t.id == '__tablename__' for t in node.targets)]
                if table_names:
                    self.assertEqual(table_names, [name.lower()])
                fks = [node.args[0].value for node in ast.walk(model) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Attribute) and node.func.attr == 'ForeignKey']
                self.assertEqual(fks, expected_fks[name])
        nickname = next(node.value for node in classes['User'].body
                        if isinstance(node, ast.Assign) and node.targets[0].id == 'nickname')
        self.assertTrue(any(item.arg == 'unique' and isinstance(item.value, ast.Constant) and item.value.value is True for item in nickname.keywords))


if __name__ == '__main__':
    unittest.main()
