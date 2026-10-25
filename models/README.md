# 공통 SQLAlchemy 모델 통합 초안

기존 `user`, `decision`, `post`, `comment` 및 INTEGER PK를 유지한다.
기존 회원 필드와 이메일·닉네임 UNIQUE도 유지한다. 이 초안은 모델 선언만 변경하며,
DB 연결·테이블 생성·데이터 삭제·마이그레이션을 실행하지 않는다.

## 확인한 코드

- 현재 작업 브랜치의 모델, 회원 Route/Service, DB 준비 도구와 테스트.
- 로컬에 저장된 `origin/feature/community` 참조 `07aaed8`의
  `models/entities.py`, `models/__init__.py`, `services/community_service.py`,
  `routes/community_routes.py`, `templates/community/index.html`.
- 원격 코드는 `git show`로만 읽었다. Checkout, Merge, Fetch는 수행하지 않았다.
  따라서 이 비교는 해당 커밋 기준이며 이후 원격 Push까지 보장하지 않는다.
- 결정·고민 기록의 신규 Service 계약은 로컬 코드에서 확인되지 않았다.

## 등록 테이블과 컬럼

모든 `id`는 INTEGER PK이며, FK도 INTEGER이다. 날짜·시간은 UTC와 timezone 지원 타입을 사용한다.
기존 컬럼의 타입·이름·FK 대상은 유지하고 필요한 컬럼을 추가했다.

| 모델 | 테이블 | 컬럼 |
| --- | --- | --- |
| User | `user` | `id`, `email`, `password_hash`, `nickname` |
| Decision | `decision` | `id`, `user_id`, `title`, `question`, `result_json`, `created_at`, `category`, `is_bookmarked`, `actual_choice`, `satisfaction_score`, `retrospective_note` |
| Post | `post` | `id`, `user_id`, `title`, `content`, `created_at`, `category`, `ai_recommendation`, `updated_at` |
| Comment | `comment` | `id`, `post_id`, `user_id`, `content`, `created_at` |
| PostOption | `post_options` | `id`, `post_id`, `name` |
| CommunityVote | `community_votes` | `id`, `post_id`, `option_id`, `user_id`, `created_at` |
| CommunityLike | `community_likes` | `id`, `post_id`, `user_id`, `created_at` |

### 결정·회고 필드

- `category`: nullable `String(80)`. 길이·카테고리 목록은 결정 담당자와 추가 합의가 필요하다.
- `is_bookmarked`: NOT NULL BOOLEAN, ORM 및 DB 기본값 `false`.
- `actual_choice`, `retrospective_note`: nullable TEXT. 실제 선택을 문자열로 저장할지는 결정·기록 담당자와 확인한다.
- `satisfaction_score`: nullable INTEGER. 이번 MVP 제안은 1~5점이며
  `ck_decision_satisfaction_score` CHECK 제약으로 NULL 또는 1~5만 허용한다.
  **고민 기록 담당자의 UI·Service와 점수 범위 합의가 필요하다.**
- 기존 `question`, `result_json`은 그대로 남아 있다.

### 커뮤니티 필드

- `Post.category`: 원격 모델과 같은 NOT NULL `String(40)`.
  카테고리를 생략하는 기존 ORM 생성 코드도 쓸 수 있도록 기본값 `기타`를 둔다.
  카테고리 목록 검증은 기존 커뮤니티 Service/Route의 계약을 따른다.
- `Post.ai_recommendation`: nullable `String(120)`. 원격 템플릿의 참조를 지원한다.
- `PostOption.name`: NOT NULL `String(120)`. `content`라는 별도 선택지 컬럼은 만들지 않는다.
- `Post.updated_at`: 생성 시 UTC 기본값 및 SQLAlchemy `onupdate`를 사용한다.
  DB 트리거는 아니며, 원격 Service도 투표·공감·댓글 변경 시 명시적으로 갱신한다.
- `Comment.created_at`, 투표·공감의 `created_at`도 원격 모델에서 확인한 필드이다.

## FK와 관계

| FK 컬럼 | 대상 |
| --- | --- |
| `decision.user_id`, `post.user_id`, `comment.user_id` | `user.id` |
| `comment.post_id`, `post_options.post_id` | `post.id` |
| `community_votes.post_id`, `community_likes.post_id` | `post.id` |
| `community_votes.user_id`, `community_likes.user_id` | `user.id` |
| `community_votes.option_id` | `post_options.id` |

- `Post.options ↔ PostOption.post`: 1:N, 선택지 id 순서.
- `Post.comments ↔ Comment.post`: 1:N, 댓글 생성 시간 순서.
- `Post.votes ↔ CommunityVote.post`, `Post.likes ↔ CommunityLike.post`: 각각 1:N.
- `PostOption.votes ↔ CommunityVote.option`: 1:N.
- `Post.author`, `Comment.author`: 각 `user_id`로 연결되는 User 관계.
- User에 확인되지 않은 역방향 속성이나 별도 Decision 관계 이름은 추가하지 않았다.

커뮤니티의 컬렉션 관계는 원격 모델과 같은 `all, delete-orphan` 정책을 사용한다.
새 선택지·투표·공감 테이블의 FK에는 원격 모델에서 확인한 `ON DELETE CASCADE`를 둔다.
특히 투표의 `option_id`는 `post_options.id ON DELETE CASCADE`이다.
기존 테이블의 FK에는 기존에 없던 ON DELETE 정책을 추가하지 않았다.
이 선언 자체로 삭제가 일어나지는 않지만, 향후 ORM에서 부모 삭제 또는 컬렉션 제거 시
자식 삭제가 전파될 수 있으므로 게시글 삭제 기능 통합 전에 정책을 확인해야 한다.

## UNIQUE / CHECK

- `user.email` UNIQUE, `user.nickname` UNIQUE 유지.
- `community_votes(post_id, user_id)` UNIQUE: `uq_community_vote_post_user`.
- `community_likes(post_id, user_id)` UNIQUE: `uq_community_like_post_user`.
- `decision.satisfaction_score`: NULL 또는 INTEGER 1~5의 CHECK 제약.

## 커뮤니티 코드 비교 및 남은 확인 사항

- `create_post()`의 `Post(..., category=...)`, `PostOption(name=...)`와 `post.options` 할당 지원.
- `list_posts()`의 `Post.options.any(PostOption.name.ilike(...))`,
  `CommunityVote.option_id`별 집계, 사용자별 투표·공감 조회 지원.
- `latest_update()`의 `Post.updated_at`, 정렬의 `created_at`,
  공감·댓글 수를 위한 `Post.likes`/`Post.comments` 컬렉션 지원.
- 템플릿의 `post.author`, `post.ai_recommendation`, `comment.author`,
  `comment.created_at`, `option.name` 지원.
- 원격의 기존 공통 테이블명 `users/decisions/posts/comments`는 채택하지 않았다.
  모든 통합 FK는 단수 `user/decision/post/comment`를 향한다.
  새 세 테이블명은 원격과 같은 `post_options/community_votes/community_likes`이다.
- 원격 `toggle_like()`는 조회한 Post를 `post`에 할당하지 않고 `post.updated_at`을 사용한다.
  모의 세션 실행에서 commit 전 `NameError`를 재현했다. 담당 Service는 수정하지 않았으며
  커뮤니티 담당자가 별도로 수정해야 한다.
- 투표·공감의 동시 요청에는 UNIQUE 충돌이 날 수 있다. 확인한 원격 Service에는
  `IntegrityError` rollback/재시도 처리가 없어 별도 합의가 필요하다.
- 선택지가 해당 게시글에 속하는지는 `cast_vote()`가 검사한다.
  두 FK만으로는 `vote.post_id == option.post_id`를 DB에서 강제하지 않으므로,
  Service를 거치지 않는 쓰기를 허용한다면 복합 FK 등 추가 설계가 필요하다.
- 원격 모델 전체를 복제하지 않았다. 회원 기능에서 사용하지 않는 `User.created_at` 및
  원격 인덱스 전체 이식은 이 초안에 포함하지 않았다.
- 실제 Neon 연결 성공은 사용자 확인 사항이며, 이번 검증에서는 재접속하지 않는다.
  실제 PostgreSQL의 제약 위반 INSERT/삭제 동작과 전체 HTTP 화면 흐름은 미검증이다.

## DB 없이 검증

프로젝트 루트의 기존 가상환경을 사용한다. 추가 패키지 설치는 필요하지 않다.

```powershell
.\.venv\Scripts\python.exe -B -m unittest tests.test_db_setup tests.test_model_integration -v
.\.venv\Scripts\python.exe -B init_db.py --preview
```

테스트는 실제 SQLAlchemy 메타데이터와 매퍼를 검사하고 PostgreSQL DDL을 메모리에서만
컴파일한다. DB 연결과 테이블 생성은 차단하며, 회원 Service의 저장·조회·commit은 모의 세션이다.
기존 `init_db.py --check`의 읽기 전용 검사는 유지한다.
실제 테이블 생성은 별도 PM 승인 전까지 실행하지 않는다.
