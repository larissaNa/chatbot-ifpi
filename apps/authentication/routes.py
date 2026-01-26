# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from flask import  render_template, redirect, request, url_for, flash
from flask_login import (
    login_required,
    current_user,
    login_user,
    logout_user
)
from apps import db, login_manager
from apps.authentication import blueprint
from apps.authentication.forms import LoginForm, CreateAccountForm, EditProfileForm
from apps.authentication.models import Users, db, DocumentoOficial, DocumentoVersao, ChromaIndexRecord, LogProcessamento
from apps.authentication.util import verify_pass
from apps.core.services.revision_service import executar_revisao_documento
from sqlalchemy import desc
from flask_sqlalchemy.pagination import Pagination

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

@blueprint.route('/perfil')
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
    return render_template('accounts/perfil-usuario.html', usuario=usuario, notificacoes=notificacoes, mensagens=mensagens)


@blueprint.route('/editar-perfil', methods=['GET', 'POST'])
@login_required
def editar_perfil():
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.perfil = form.perfil.data

        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
        return redirect(url_for('authentication_blueprint.perfil_usuario'))
    elif request.method == 'POST':
        # Exibe erros do formulário (opcional: console ou logs)
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro no campo '{getattr(form, field).label.text}': {error}", 'danger')

    return render_template('accounts/editar-perfil.html', form=form, usuario=current_user)

#SERVIÇOS#


@blueprint.route("/admin/docs", methods=["GET", "POST"])
# @login_required
# @admin_required
def admin_docs():
    if request.method == "POST":
        titulo = request.form.get("titulo")
        url = request.form.get("url")
        descricao = request.form.get("descricao")

        if not titulo or not url:
            flash("Título e URL são obrigatórios!", "danger")
        else:
            doc = DocumentoOficial(titulo=titulo, url=url, descricao=descricao)
            db.session.add(doc)
            db.session.commit()
            flash("Documento adicionado com sucesso!", "success")

        return redirect(url_for("authentication_blueprint.admin_docs"))

    documentos = DocumentoOficial.query.order_by(DocumentoOficial.criado_em.desc()).all()
    return render_template("admin/admin-docs.html", documentos=documentos)

# === Painel: listar fontes

@blueprint.route("/admin/docs/delete/<int:id>", methods=["POST"])
# @login_required
# @admin_required
def deletar_doc(id):
    doc = DocumentoOficial.query.get_or_404(id)
    db.session.delete(doc)
    db.session.commit()
    flash("Documento removido com sucesso!", "info")
    return redirect(url_for("authentication_blueprint.admin_docs"))

@blueprint.route("/admin/docs/<int:doc_id>")
@login_required
@admin_required
def admin_doc_detail(doc_id):
    doc = DocumentoOficial.query.get_or_404(doc_id)
    versoes = DocumentoVersao.query.filter_by(documento_id=doc.id).order_by(desc(DocumentoVersao.criado_em)).all()
    return render_template("admin/doc_detail.html", doc=doc, versoes=versoes)

# === Visualizar todas as versões (global) ===
@blueprint.route("/admin/versions")
@login_required
@admin_required
def admin_versions():
    versoes = DocumentoVersao.query.order_by(desc(DocumentoVersao.criado_em)).limit(200).all()
    return render_template("admin/versions.html", versoes=versoes)

# === Visualizar logs do processamento ===
@blueprint.route("/admin/logs")
@login_required
@admin_required
def admin_logs():
    page = int(request.args.get("page", 1))
    per_page = 50
    query = LogProcessamento.query.order_by(desc(LogProcessamento.criado_em))
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    logs = pagination.items
    return render_template("admin/logs.html", logs=logs, pagination=pagination)

# === Ações rápidas (POSTs) ===
@blueprint.route("/admin/docs/toggle/<int:doc_id>", methods=["POST"])
@login_required
@admin_required
def admin_toggle_doc(doc_id):
    doc = DocumentoOficial.query.get_or_404(doc_id)
    
    if doc.obsoleto:
        flash("Documento marcado como obsoleto não pode ser reativado.", "danger")
        return redirect(url_for("authentication_blueprint.admin_docs"))
        
    doc.ativo = not doc.ativo
    db.session.commit()
    flash(f"Documento {'ativado' if doc.ativo else 'desativado'} com sucesso.", "success")
    return redirect(url_for("authentication_blueprint.admin_docs"))

@blueprint.route("/admin/docs/confirm-obsolete/<int:doc_id>", methods=["POST"])
@login_required
@admin_required
def admin_confirm_obsolete(doc_id):
    doc = DocumentoOficial.query.get_or_404(doc_id)
    doc.obsoleto = True
    doc.sugerido_obsoleto = False # Limpa a sugestão pois já foi confirmado
    doc.ativo = False # Desativa automaticamente
    db.session.commit()
    flash("Documento marcado como obsoleto definitivamente.", "success")
    return redirect(url_for("authentication_blueprint.admin_docs"))

@blueprint.route("/admin/versions/mark-obsolete/<int:versao_id>", methods=["POST"])
@login_required
@admin_required
def admin_mark_obsolete(versao_id):
    v = DocumentoVersao.query.get_or_404(versao_id)
    v.status_processamento = "obsoleto"
    db.session.commit()
    flash("Versão marcada como obsoleta.", "success")
    return redirect(request.referrer or url_for("authentication_blueprint.admin_versions"))

# Trigger manual: executar search/extract/process (apenas cria um log; a execução real será implementada quando integrar agentes)
@blueprint.route("/admin/trigger/<string:agente>", methods=["POST"])
@login_required
@admin_required
def admin_trigger_agent(agente):
    # registra log; quando integrar agentes você pode chamar filas/tarefas aqui
    log = LogProcessamento(
        versao_id = None,
        agente = agente,
        acao = "manual_trigger",
        detalhe = f"Trigger manual pelo usuário {current_user.username}"
    )
    db.session.add(log)
    db.session.commit()
    flash(f"Agente '{agente}' acionado manualmente (log criado).", "info")
    return redirect(request.referrer or url_for("authentication_blueprint.admin_docs"))


@blueprint.route("/admin/docs/revisar/<int:doc_id>", methods=["POST"])
@login_required
@admin_required
def admin_revisar_doc(doc_id):
    try:
        resultado = executar_revisao_documento(doc_id)
        if resultado.get("status") == "sucesso":
            flash(f"Revisão concluída: {resultado.get('acao')} - {resultado.get('justificativa')}", "success")
        else:
            flash(f"Erro na revisão: {resultado.get('mensagem')}", "danger")
    except Exception as e:
        flash(f"Erro crítico ao executar revisão: {str(e)}", "danger")
        
    return redirect(request.referrer or url_for("authentication_blueprint.admin_docs"))


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
