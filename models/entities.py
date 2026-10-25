from datetime import datetime, timezone
from extensions import db


class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(80), unique=True, nullable=False)


class Decision(db.Model):
    __tablename__ = 'decision'
    __table_args__ = (
        db.CheckConstraint(
            'satisfaction_score IS NULL OR satisfaction_score BETWEEN 1 AND 5',
            name='ck_decision_satisfaction_score'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    question = db.Column(db.Text, nullable=False, default='')
    result_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    category = db.Column(db.String(80), nullable=False, default='일반', server_default='일반', index=True)
    is_bookmarked = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    actual_choice = db.Column(db.Text, nullable=True)
    satisfaction_score = db.Column(db.Integer, nullable=True)
    retrospective_note = db.Column(db.Text, nullable=True)


class Post(db.Model):
    __tablename__ = 'post'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    category = db.Column(db.String(40), nullable=False, default='기타')
    ai_recommendation = db.Column(db.String(120), nullable=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    author = db.relationship('User')
    options = db.relationship(
        'PostOption', back_populates='post', cascade='all, delete-orphan', order_by='PostOption.id')
    comments = db.relationship(
        'Comment', back_populates='post', cascade='all, delete-orphan', order_by='Comment.created_at')
    likes = db.relationship('CommunityLike', back_populates='post', cascade='all, delete-orphan')
    votes = db.relationship('CommunityVote', back_populates='post', cascade='all, delete-orphan')


class Comment(db.Model):
    __tablename__ = 'comment'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    post = db.relationship('Post', back_populates='comments')
    author = db.relationship('User')


class PostOption(db.Model):
    __tablename__ = 'post_options'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(120), nullable=False)

    post = db.relationship('Post', back_populates='options')
    votes = db.relationship('CommunityVote', back_populates='option', cascade='all, delete-orphan')


class CommunityVote(db.Model):
    __tablename__ = 'community_votes'
    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='uq_community_vote_post_user'),
    )

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('post_options.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    post = db.relationship('Post', back_populates='votes')
    option = db.relationship('PostOption', back_populates='votes')


class CommunityLike(db.Model):
    __tablename__ = 'community_likes'
    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='uq_community_like_post_user'),
    )

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    post = db.relationship('Post', back_populates='likes')