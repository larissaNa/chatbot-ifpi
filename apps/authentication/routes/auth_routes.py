# -*- encoding: utf-8 -*-
"""
Rotas de autenticacao e registro.
"""

from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user

from apps import db
from apps.authentication import blueprint
from apps.authentication.forms import CreateAccountForm, LoginForm
from apps.authentication import Users
from apps.authentication.util import verify_pass


@blueprint.route("/")
def route_default():
    return redirect(url_for("authentication_blueprint.login"))


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    login_form = LoginForm(request.form)
    if "login" in request.form:
        username = request.form["username"]
        password = request.form["password"]

        user = Users.query.filter_by(username=username).first()
        if user and verify_pass(password, user.password):
            login_user(user)
            return redirect(url_for("authentication_blueprint.route_default"))

        return render_template(
            "accounts/login.html",
            msg="Wrong user or password",
            form=login_form,
        )

    if not current_user.is_authenticated:
        return render_template("accounts/login.html", form=login_form)
    return redirect(url_for("home_blueprint.index"))


@blueprint.route("/register", methods=["GET", "POST"])
def register():
    create_account_form = CreateAccountForm(request.form)
    if "register" in request.form:
        username = request.form["username"]
        email = request.form["email"]

        user = Users.query.filter_by(username=username).first()
        if user:
            return render_template(
                "accounts/register.html",
                msg="Username already registered",
                success=False,
                form=create_account_form,
            )

        user = Users.query.filter_by(email=email).first()
        if user:
            return render_template(
                "accounts/register.html",
                msg="Email already registered",
                success=False,
                form=create_account_form,
            )

        user = Users(**request.form)
        db.session.add(user)
        db.session.commit()
        logout_user()

        return render_template(
            "accounts/register.html",
            msg="User created successfully.",
            success=True,
            form=create_account_form,
        )

    return render_template("accounts/register.html", form=create_account_form)


@blueprint.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("authentication_blueprint.login"))
