# PickMe Flask community implementation

기존 Flask 스타터에 커뮤니티 기능을 포함한 프로젝트입니다. 기본 모델은 PostgreSQL과 SQLAlchemy를 사용하며, 실제 DB 접속 주소는 `.env`의 `DATABASE_URL`에 설정합니다. `.env.example`을 `.env`로 복사한 뒤 DB 제공자가 준 값으로 바꾸세요. `.env`에는 비밀번호가 들어갈 수 있으므로 GitHub에 올리지 마세요.

## 시연 영상
링크: https://www.youtube.com/watch?v=5Bapf1U08GI

## PostgreSQL 연결 준비

1. PostgreSQL에서 DB와 앱 전용 사용자를 준비하고, 해당 사용자에게 DB 접속 및 스키마 생성 권한을 부여합니다.
2. `.env.example`을 `.env`로 복사합니다.
3. `DATABASE_URL`을 `postgresql+psycopg://사용자:비밀번호@호스트:5432/DB이름` 형식으로 입력합니다. 비밀번호에 `@`, `/`, `#`, `:` 등이 포함되면 URL 인코딩이 필요할 수 있습니다.
4. `SECRET_KEY`도 충분히 긴 임의 문자열로 바꿉니다.
5. 의존성을 설치합니다: `pip install -r requirements.txt`

`config.py`는 PostgreSQL URL에 psycopg 3 드라이버를 사용하고 DB 연결이 끊겼다가 복구된 경우를 감지하도록 설정합니다. `postgres://` 또는 `postgresql://` 형식도 psycopg 3 URL로 보정합니다. 개발용 기본값은 `sqlite:///pickme.db`입니다.

## 스키마 생성 및 변경

기본 SQLite 개발 모드에서는 앱 시작 시 `db.create_all()`이 빠진 테이블을 생성합니다. PostgreSQL에서는 `AUTO_CREATE_DB=false`로 두고, `app.py`가 SQLAlchemy와 Flask-Migrate를 초기화하며 DB 스키마를 마이그레이션으로 관리합니다. `db.create_all()`은 기존 테이블의 컬럼을 변경하지 않습니다. PostgreSQL DB에 접속할 수 있고 모델 정의가 확정된 뒤, 프로젝트 루트에서 최초 한 번 실행합니다.

```powershell
flask --app app db init
flask --app app db migrate -m "initial schema"
flask --app app db upgrade
```

생성된 `migrations/` 폴더와 파일은 Git에 커밋해야 합니다. 이후 `models/entities.py`에서 테이블이나 컬럼을 바꿀 때마다 새 마이그레이션을 만들고 적용합니다.

```powershell
flask --app app db migrate -m "describe schema change"
flask --app app db upgrade
```

`migrate`가 생성한 파일은 적용 전에 꼭 검토하세요. 테이블·컬럼 이름이나 DB 설계가 팀이 정한 스키마와 다르면 마이그레이션을 적용하기 전에 `models/entities.py`를 먼저 맞춰야 합니다. PostgreSQL에서는 `AUTO_CREATE_DB=false`를 유지하고, `db.create_all()` 대신 마이그레이션으로 스키마를 관리합니다. 로컬 SQLite에서만 자동 테이블 생성을 사용합니다.

## 앱 실행

```powershell
python app.py
```

또는 배포 시 `gunicorn 'app:app'`을 사용합니다. PostgreSQL 서버·DB·사용자·권한은 앱과 별도로 준비되어 있어야 합니다.

## 모델 구조

테이블과 컬럼 정의는 `models/entities.py`에 있습니다. 현재 모델은 `users`, `decisions`, `posts`, `post_options`, `community_votes`, `community_likes`, `comments` 테이블을 정의합니다. 외부에서 별도 스키마를 이미 만들 예정이면 이 파일의 테이블명, 컬럼명, 자료형, 제약조건과 일치하는지 확인하고 마이그레이션을 적용하세요.

커뮤니티 요청은 `routes/community_routes.py`, DB 읽기/쓰기는 `services/community_service.py`에 있습니다. DB 주소만 바꾸는 경우 이 두 파일은 보통 수정하지 않습니다. DB 스키마를 다르게 정했다면 모델과 쿼리가 그 스키마에 맞는지 확인해야 합니다.

## 주의

- `.env`와 실제 DB 비밀번호를 Git에 커밋하지 마세요.
- 운영 DB에서 마이그레이션을 적용하기 전에 백업하고, 생성된 마이그레이션 내용을 확인하세요.
- `requirements.txt`에는 PostgreSQL 드라이버 `psycopg[binary]`와 스키마 변경 도구 `Flask-Migrate`가 포함되어 있습니다.
- 로컬 기본 SQLite는 `users` 등 필요한 테이블을 자동 생성하므로 `python app.py`로 시작할 수 있습니다. PostgreSQL에서는 접속 정보와 모델 정의가 확정된 뒤 마이그레이션을 적용해야 합니다.


