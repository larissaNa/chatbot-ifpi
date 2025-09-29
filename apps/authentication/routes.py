# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""
from flask import Response, render_template, redirect, request, url_for, flash
from flask_login import (
    login_required,
    current_user,
    login_user,
    logout_user
)
# from .models import ResultadoConsulta, db, UserCredits, CreditOperation
from apps import db, login_manager
from apps.integracoes.utils import get_instagram_avatar, getpost, salvar_imagem_local, APIKEY_VORTICE
from apps.integracoes.instagram_connector import InstagramConnector
from apps.integracoes.clientes import executar_consulta, APINaoDefinida
from apps.authentication import blueprint
from apps.authentication.forms import LoginForm, CreateAccountForm
from apps.authentication.models import Users, db
from apps.authentication.util import verify_pass


@blueprint.route('/')
def route_default():
    return redirect(url_for('authentication_blueprint.login'))

# Middleware para acesso restrito a admin
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acesso não autorizado.", "danger")
            return redirect(url_for("home_blueprint.index"))
        return func(*args, **kwargs)
    return decorated_view

# Login & Registration

@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm(request.form)
    if 'login' in request.form:

        # read form data
        username = request.form['username']
        password = request.form['password']

        # Locate user
        user = Users.query.filter_by(username=username).first()

        # Check the password
        if user and verify_pass(password, user.password):

            login_user(user)
            return redirect(url_for('authentication_blueprint.route_default'))

        # Something (user or pass) is not ok
        return render_template('accounts/login.html',
                               msg='Wrong user or password',
                               form=login_form)

    if not current_user.is_authenticated:
        return render_template('accounts/login.html',
                               form=login_form)
    return redirect(url_for('home_blueprint.index'))


@blueprint.route('/register', methods=['GET', 'POST'])
def register():
    create_account_form = CreateAccountForm(request.form)
    if 'register' in request.form:

        username = request.form['username']
        email = request.form['email']

        # Check usename exists
        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Username already registered',
                                   success=False,
                                   form=create_account_form)

        # Check email exists
        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template('accounts/register.html',
                                   msg='Email already registered',
                                   success=False,
                                   form=create_account_form)

        # else we can create the user
        user = Users(**request.form)
        db.session.add(user)
        db.session.commit()

        # Delete user from session
        logout_user()

        return render_template('accounts/register.html',
                               msg='User created successfully.',
                               success=True,
                               form=create_account_form)

    else:
        return render_template('accounts/register.html', form=create_account_form)


@blueprint.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('authentication_blueprint.login')) 


@blueprint.route("/contas/delete/<int:id>", methods=["POST"])
@login_required
def delete_conta(id):
    conta = ContaSocial.query.get_or_404(id)
    if conta.usuario_id != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for("authentication_blueprint.contas"))
    db.session.delete(conta)
    db.session.commit()
    flash("Conta excluída.", "success")
    return redirect(url_for("authentication_blueprint.contas"))

# ------------------- CONSULTA -------------------

from flask import Blueprint, render_template

@blueprint.route("/erro-api-nao-definida")
@login_required
def erro_api_nao_definida():
    return render_template("home/erro-api-nao-definida.html"), 400

def get_avatar_url(profile_id: str, rede: str) -> str:
    rede = (rede or "").strip().lower()

    if rede == "instagram":
        return get_instagram_avatar(profile_id)

    elif rede == "facebook":
        return f"https://graph.facebook.com/{profile_id}/picture?type=large"

    # outras redes podem ser adicionadas aqui com regras específicas
    else:
        return "/static/assets/image/avatar.png"

@blueprint.route("/proxy-image")
def proxy_image():
    import requests
    url = request.args.get("url")
    response = requests.get(url, stream=True)
    return Response(response.raw, content_type=response.headers["Content-Type"])

# Errors

@login_manager.unauthorized_handler
def unauthorized_handler():
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(403)
def access_forbidden(error):
    return render_template('home/page-403.html'), 403


@blueprint.errorhandler(404)
def not_found_error(error):
    return render_template('home/page-404.html'), 404


@blueprint.errorhandler(500)
def internal_error(error):
    return render_template('home/page-500.html'), 500
