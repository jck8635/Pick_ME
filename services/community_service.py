"""Community read/write operations. Routes stay thin; DB changes live here."""
from sqlalchemy import or_, func
from datetime import datetime, timezone
from extensions import db
from models import Post, PostOption, CommunityVote, CommunityLike, Comment

CATEGORIES = ('음식/식사', '진로/이직', '쇼핑/소비', '연애/관계', '일상/생활', '학습/자기계발', '여행/여가', '기타')

def latest_update():
    latest = db.session.query(func.max(Post.updated_at)).scalar()
    return latest.isoformat() if latest else ''

def list_posts(category=None, query=None, user_id=None):
    base = Post.query
    if category in CATEGORIES:
        base = base.filter(Post.category == category)
    if query:
        pattern = f'%{query.strip()}%'
        base = base.filter(or_(Post.title.ilike(pattern), Post.content.ilike(pattern), Post.options.any(PostOption.name.ilike(pattern))))
    posts = base.order_by(Post.created_at.desc()).all()
    votes = {v.post_id: v.option_id for v in CommunityVote.query.filter_by(user_id=user_id).all()} if user_id else {}
    liked = {x.post_id for x in CommunityLike.query.filter_by(user_id=user_id).all()} if user_id else set()
    counts = dict(db.session.query(CommunityVote.option_id, func.count(CommunityVote.id)).group_by(CommunityVote.option_id).all())
    return posts, votes, liked, counts

def top_posts_by_engagement(metric, limit=3):
    """Return global community posts ranked by likes or comments."""
    posts = Post.query.all()
    if metric == 'comments':
        posts.sort(key=lambda post: (len(post.comments), post.created_at, post.id), reverse=True)
    else:
        posts.sort(key=lambda post: (len(post.likes), post.created_at, post.id), reverse=True)
    return posts[:limit]

def create_post(user, title, content, category, option_names):
    post = Post(user_id=user.id, title=title.strip(), content=content.strip(), category=category)
    post.options = [PostOption(name=name.strip()) for name in option_names if name.strip()]
    db.session.add(post)
    db.session.commit()
    return post

def cast_vote(post_id, option_id, user_id):
    post, option = db.session.get(Post, post_id), db.session.get(PostOption, option_id)
    if not post or not option or option.post_id != post.id:
        return False, '올바르지 않은 선택지입니다.'
    vote = CommunityVote.query.filter_by(post_id=post.id, user_id=user_id).first()
    if vote:
        vote.option_id = option.id
    else:
        db.session.add(CommunityVote(post_id=post.id, option_id=option.id, user_id=user_id))
    post.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True, '투표가 반영되었습니다.'

def toggle_like(post_id, user_id):
    post = db.session.get(Post, post_id)
    if post is None:
        return False
    like = CommunityLike.query.filter_by(post_id=post_id, user_id=user_id).first()
    if like: db.session.delete(like)
    else: db.session.add(CommunityLike(post_id=post_id, user_id=user_id))
    post.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True

def add_comment(post_id, user, content):
    post = db.session.get(Post, post_id)
    if post is None: return False
    db.session.add(Comment(post_id=post_id, user_id=user.id, content=content.strip()))
    post.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True



def cancel_vote(post_id, user_id):
    """Remove the current user's vote for a post."""
    post = db.session.get(Post, post_id)
    if post is None:
        return False, '게시글을 찾을 수 없습니다.'
    vote = CommunityVote.query.filter_by(post_id=post_id, user_id=user_id).first()
    if vote is None:
        return True, '취소할 투표가 없습니다.'
    db.session.delete(vote)
    post.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return True, '투표를 취소했습니다.'


def edit_post(post_id, user_id, title, content, category):
    post = db.session.get(Post, post_id)

    if post is None or post.user_id != user_id:
        return False

    post.title = title.strip()
    post.content = content.strip()
    post.category = category
    post.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    return True


def delete_post(post_id, user_id):
    post = db.session.get(Post, post_id)

    if post is None or post.user_id != user_id:
        return False

    db.session.delete(post)
    db.session.commit()
    return True


def edit_comment(post_id, comment_id, user_id, content):
    comment = db.session.get(Comment, comment_id)

    if (
        comment is None
        or comment.post_id != post_id
        or comment.user_id != user_id
    ):
        return False

    comment.content = content.strip()
    comment.post.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    return True


def delete_comment(post_id, comment_id, user_id):
    comment = db.session.get(Comment, comment_id)

    if (
        comment is None
        or comment.post_id != post_id
        or comment.user_id != user_id
    ):
        return False

    post = comment.post
    db.session.delete(comment)
    post.updated_at = datetime.now(timezone.utc)

    db.session.commit()
    return True
