# -*- encoding: utf-8 -*-
"""
Rotas relacionadas ao perfil do usuario autenticado.
"""

from flask import flash, render_template, request, url_for, redirect
from flask_login import current_user, login_required

from apps import db
from apps.authentication import blueprint
from apps.authentication.forms import EditProfileForm


@blueprint.route("/perfil")
@login_required
def perfil_usuario():
    usuario = current_user
    notificacoes = [
        {"titulo": "Senha alterada", "hora": "Ontem, 18:45"},
    ]
    mensagens = [
        {"de": "Admin", "assunto": "Bem-vindo!", "hora": "Ontem"},
        {"de": "Suporte", "assunto": "Atualização de sistema", "hora": "2 dias atrás"},
    ]
    return render_template(
        "accounts/perfil-usuario.html",
        usuario=usuario,
        notificacoes=notificacoes,
        mensagens=mensagens,
    )


@blueprint.route("/editar-perfil", methods=["GET", "POST"])
@login_required
def editar_perfil():
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.perfil = form.perfil.data

        db.session.commit()
        flash("Perfil atualizado com sucesso!", "success")
        return redirect(url_for("authentication_blueprint.perfil_usuario"))

    if request.method == "POST":
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro no campo '{getattr(form, field).label.text}': {error}", "danger")

    return render_template("accounts/editar-perfil.html", form=form, usuario=current_user)
