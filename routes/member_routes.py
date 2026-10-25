from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, session, g, flash

from services import member_service

bp = Blueprint('member', __name__, url_prefix='/member')


def login_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not g.get('user'):
            flash('로그인이 필요합니다.')
            return redirect(url_for('member.login'))
        return fn(*args, **kwargs)
    return decorated


@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if g.get('user'):
        return redirect(url_for('member.mypage'))
    if request.method == 'POST':
        try:
            member_service.register_member(
                request.form.get('email', ''), request.form.get('nickname', ''),
                request.form.get('password', ''))
        except member_service.MemberError as error:
            flash(str(error))
        else:
            flash('회원가입되었습니다. 로그인해주세요.')
            return redirect(url_for('member.login'))
    return render_template('member/signup.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.get('user'):
        return redirect(url_for('member.mypage'))
    if request.method == 'POST':
        try:
            user = member_service.authenticate_member(
                request.form.get('email', ''), request.form.get('password', ''))
        except member_service.MemberError as error:
            flash(str(error))
        else:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('main.index'))
    return render_template('member/login.html')


@bp.post('/logout')
def logout():
    session.clear()
    flash('로그아웃되었습니다.')
    return redirect(url_for('main.index'))


@bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'nickname':
                member_service.change_nickname(g.user, request.form.get('nickname', ''))
                flash('닉네임을 변경했습니다.')
            elif action == 'password':
                member_service.change_password(
                    g.user, request.form.get('current_password', ''),
                    request.form.get('new_password', ''),
                    request.form.get('password_confirmation', ''))
                user_id = g.user.id
                session.clear()
                session['user_id'] = user_id
                flash('비밀번호를 변경했습니다.')
            else:
                raise member_service.MemberError('변경할 회원 정보를 확인해주세요.')
        except member_service.MemberError as error:
            flash(str(error))
        else:
            return redirect(url_for('member.mypage'))
    return render_template('member/mypage.html')
