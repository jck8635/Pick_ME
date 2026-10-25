"""Neon DB 준비 도구. 기본 실행은 DB에 접속하지 않는 모델 목록 확인이다.

프로젝트 루트에서 기존 가상환경의 Python으로 실행한다.
  python init_db.py                         # 모델/테이블 검토, DB 접속 없음
  python init_db.py --check                 # 읽기 전용 PostgreSQL 연결 확인
  python init_db.py --create --pm-approved  # PM 승인 후에만 실행할 최초 생성

기존 테이블/데이터를 삭제하지 않으며, 기존 테이블에 UNIQUE를 추가하거나
SQLite 데이터를 PostgreSQL로 복사하지 않는다. 이는 별도 마이그레이션 작업이다.
연결 문자열, 비밀번호, SECRET_KEY, 원본 DB 예외는 출력하지 않는다.
"""

import argparse
import sys


class SetupError(ValueError):
    """비밀 값이 포함되지 않은 안내 메시지만 사용한다."""


def _load_runtime():
    # --help와 오프라인 테스트에는 Flask/DB 패키지가 필요하지 않다.
    # app.py에는 더 이상 자동 테이블 생성이 없다.
    from app import app
    from extensions import db

    return app, db


def _validate_target(url):
    if url.drivername != 'postgresql+psycopg':
        raise SetupError(
            'DATABASE_URL을 PostgreSQL + psycopg 3 형식으로 설정해주세요. '
            'SQLite 등 다른 DB에서는 이 도구를 실행하지 않습니다.')
    if url.database != 'neondb':
        raise SetupError('이 팀의 대상 데이터베이스는 neondb입니다. DATABASE_URL을 확인해주세요.')


def _print_models(db):
    print('등록된 SQLAlchemy 모델 → 테이블:', flush=True)
    for mapper in sorted(db.Model.registry.mappers, key=lambda item: item.class_.__name__):
        print(f'  {mapper.class_.__name__} → {mapper.local_table.fullname}', flush=True)
    print('등록된 테이블 (FK 의존 순서):', flush=True)
    for table in db.metadata.sorted_tables:
        print(f'  {table.fullname}', flush=True)
    print('기존 테이블의 구조/제약은 create_all()로 변경되지 않습니다.', flush=True)
    print('기존 user 테이블의 nickname UNIQUE 적용은 별도 마이그레이션이 필요합니다.', flush=True)


def _check_connection(db):
    # 트랜잭션을 시작하기 전에 psycopg의 READ ONLY 특성을 설정한다.
    # 테이블이 아직 없어도 실행할 수 있으며 회원 데이터는 조회하지 않는다.
    with db.engine.connect() as connection:
        connection = connection.execution_options(postgresql_readonly=True)
        with connection.begin():
            row = connection.exec_driver_sql(
                "SELECT 1 AS connected, current_database() AS database_name, "
                "current_setting('transaction_read_only') AS transaction_read_only"
            ).one()
            if row.connected != 1 or row.database_name != 'neondb':
                raise SetupError('대상 데이터베이스 연결 검증에 실패했습니다.')
            if row.transaction_read_only != 'on':
                raise SetupError('읽기 전용 트랜잭션이 확인되지 않았습니다.')
    print('연결 확인 완료: PostgreSQL / neondb / 읽기 전용 트랜잭션', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--preview', action='store_true', help='모델/테이블 목록만 출력 (기본값, DB 접속 없음)')
    actions.add_argument('--check', action='store_true', help='읽기 전용 PostgreSQL 연결 확인')
    actions.add_argument('--create', action='store_true', help='없는 테이블만 생성 (PM 승인 필수)')
    parser.add_argument('--pm-approved', action='store_true', help='최초 생성에 대한 PM 승인을 받았음을 명시')
    args = parser.parse_args(argv)
    if args.create and not args.pm_approved:
        parser.error('실제 테이블 생성은 PM 승인 후 --create --pm-approved로 실행해주세요.')
    if args.pm_approved and not args.create:
        parser.error('--pm-approved는 --create와 함께 사용할 때만 유효합니다.')

    try:
        app, db = _load_runtime()
        with app.app_context():
            _validate_target(db.engine.url)
            _print_models(db)
            if args.check:
                _check_connection(db)
            elif args.create:
                print('승인된 최초 초기화: 없는 테이블만 생성합니다. 삭제/초기화/ALTER는 수행하지 않습니다.', flush=True)
                db.create_all()
                print('테이블 생성 확인을 완료했습니다. 기존 테이블과 데이터는 유지됩니다.', flush=True)
            else:
                print('검토 모드: DB 연결과 테이블 생성을 수행하지 않았습니다.', flush=True)
        return 0
    except ModuleNotFoundError:
        print('필수 패키지를 찾지 못했습니다. requirements.txt가 준비된 기존 가상환경을 사용해주세요.', file=sys.stderr)
    except SetupError as error:
        print(str(error), file=sys.stderr)
    except Exception:
        # SQLAlchemy/psycopg 예외에는 URL 또는 자격 증명이 포함될 수 있다.
        print('DB 준비 작업을 완료하지 못했습니다. 연결 설정·패키지·권한을 확인해주세요. '
              '보안을 위해 상세 오류는 출력하지 않습니다.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
