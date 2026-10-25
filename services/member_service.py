"""회원 입력 검증과 SQLAlchemy 기반 회원 비즈니스 로직."""

import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User


class MemberError(ValueError):
    """화면에 안전하게 표시할 수 있는 회원 처리 오류."""


def _email(value):
    email = value.strip().lower()
    if not email:
        raise MemberError('이메일을 입력해주세요.')
    if len(email) > 255:
        raise MemberError('이메일은 255자 이내로 입력해주세요.')
    if email.count('@') != 1:
        raise MemberError('올바른 이메일 형식으로 입력해주세요.')
    local, domain = email.split('@')
    labels = domain.split('.')
    if (
        not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}", local)
        or local.startswith('.') or local.endswith('.') or '..' in local
        or len(labels) < 2
        or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
               for label in labels)
        or len(labels[-1]) < 2
    ):
        raise MemberError('올바른 이메일 형식으로 입력해주세요.')
    return email


def _nickname(value):
    nickname = value.strip()
    if not nickname:
        raise MemberError('닉네임을 입력해주세요.')
    if len(nickname) > 80:
        raise MemberError('닉네임은 80자 이내로 입력해주세요.')
    if any(ord(char) < 32 or ord(char) == 127 for char in nickname):
        raise MemberError('닉네임에는 줄바꿈이나 제어 문자를 사용할 수 없습니다.')
    return nickname


def _password(value):
    if len(value) < 8 or not value.strip():
        raise MemberError('비밀번호는 공백만 사용하지 않고 8자 이상 입력해주세요.')
    if len(value) > 1024:
        raise MemberError('비밀번호는 1,024자 이내로 입력해주세요.')
    return value


def _matches_password(user, password):
    if not password or len(password) > 1024:
        return False
    try:
        return check_password_hash(user.password_hash, password)
    except (ValueError, TypeError):
        return False


def _rollback_error(message):
    db.session.rollback()
    return MemberError(message)


def register_member(email, nickname, password):
    email, nickname, password = _email(email), _nickname(nickname), _password(password)
    try:
        if db.session.scalar(select(User).where(func.lower(User.email) == email)):
            raise MemberError('이미 가입된 이메일입니다.')
        if db.session.scalar(select(User).where(User.nickname == nickname)):
            raise MemberError('이미 사용 중인 닉네임입니다.')
        user = User(email=email, nickname=nickname,
                    password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        return user
    except IntegrityError:
        raise _rollback_error('이미 사용 중인 회원 정보입니다. 이메일과 닉네임을 확인해주세요.') from None
    except SQLAlchemyError:
        raise _rollback_error('회원가입을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.') from None


def authenticate_member(email, password):
    email = _email(email)
    if not password:
        raise MemberError('비밀번호를 입력해주세요.')
    if len(password) > 1024:
        raise MemberError('이메일 또는 비밀번호가 올바르지 않습니다.')
    try:
        user = db.session.scalar(select(User).where(func.lower(User.email) == email))
    except SQLAlchemyError:
        raise _rollback_error('로그인을 처리하지 못했습니다. 잠시 후 다시 시도해주세요.') from None
    if not user or not _matches_password(user, password):
        raise MemberError('이메일 또는 비밀번호가 올바르지 않습니다.')
    return user


def change_nickname(user, nickname):
    nickname = _nickname(nickname)
    try:
        duplicate = db.session.scalar(select(User).where(
            User.nickname == nickname, User.id != user.id))
        if duplicate:
            raise MemberError('이미 사용 중인 닉네임입니다.')
        user.nickname = nickname
        db.session.commit()
    except IntegrityError:
        raise _rollback_error('이미 사용 중인 닉네임입니다.') from None
    except SQLAlchemyError:
        raise _rollback_error('닉네임을 변경하지 못했습니다. 잠시 후 다시 시도해주세요.') from None


def change_password(user, current_password, new_password, confirmation):
    if not _matches_password(user, current_password):
        raise MemberError('현재 비밀번호가 올바르지 않습니다.')
    new_password = _password(new_password)
    if new_password != confirmation:
        raise MemberError('새 비밀번호와 비밀번호 확인이 일치하지 않습니다.')
    if _matches_password(user, new_password):
        raise MemberError('현재 비밀번호와 다른 새 비밀번호를 입력해주세요.')
    try:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
    except SQLAlchemyError:
        raise _rollback_error('비밀번호를 변경하지 못했습니다. 잠시 후 다시 시도해주세요.') from None
