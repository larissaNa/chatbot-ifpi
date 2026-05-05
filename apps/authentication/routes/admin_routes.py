# -*- encoding: utf-8 -*-
"""
Rotas administrativas relacionadas a documentos, versoes, logs e feedbacks.
"""

import re
import os
import uuid
from werkzeug.utils import secure_filename
from flask import flash, redirect, render_template, request, url_for, current_app
from sqlalchemy import desc, select

from flask_login import current_user, login_required

from apps import db
from apps.authentication import blueprint
from apps.authentication.decorators import admin_required
from apps.authentication import (
    ChatFeedback,
    DocumentoOficial,
    DocumentoVersao,
    LogProcessamento,
)
from apps.core.documents.services.revision_orchestrator import executar_revisao_documento


def _normalize_feedback_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _classify_feedback_failure(feedback: ChatFeedback) -> str:
    answer = _normalize_feedback_text(feedback.answer)
    thoughts = _normalize_feedback_text(getattr(getattr(feedback, "bot_message", None), "thoughts", ""))

    if not answer:
        return "Resposta vazia"
    if "não encontrei" in answer or "não localizei" in answer or "rag_status" in thoughts and "not_found" in thoughts:
        return "RAG sem contexto suficiente"
    if "tavily_web" in thoughts or '"route": "tavily_web"' in thoughts:
        return "Fallback para web"
    if len(answer) < 140:
        return "Resposta curta ou genérica"
    return "Necessita reformulação"


def _feedback_dashboard_data(feedbacks: list[ChatFeedback]) -> dict:
    failure_counts: dict[str, int] = {}
    repeated_questions: dict[str, dict[str, int | str]] = {}
    revised_count = 0

    for feedback in feedbacks:
        label = _classify_feedback_failure(feedback)
        failure_counts[label] = failure_counts.get(label, 0) + 1

        if (feedback.comment or "").strip():
            revised_count += 1

        normalized_question = _normalize_feedback_text(feedback.question)
        if normalized_question:
            row = repeated_questions.setdefault(
                normalized_question,
                {
                    "question": (feedback.question or "").strip(),
                    "count": 0,
                },
            )
            row["count"] = int(row["count"]) + 1

    recurrent_failures = [
        {"label": label, "count": count}
        for label, count in sorted(failure_counts.items(), key=lambda item: item[1], reverse=True)
    ]
    recurring_questions = sorted(
        repeated_questions.values(),
        key=lambda item: int(item["count"]),
        reverse=True,
    )

    stats = {
        "total_down": len(feedbacks),
        "revised_count": revised_count,
        "top_failure": recurrent_failures[0]["label"] if recurrent_failures else "Sem dados",
    }
    return {
        "stats": stats,
        "recurrent_failures": recurrent_failures[:5],
        "recurring_questions": recurring_questions[:5],
    }


@blueprint.route("/admin/docs", methods=["GET", "POST"])
@login_required
@admin_required
def admin_docs():
    if request.method == "POST":
        titulo = request.form.get("titulo")
        url = request.form.get("url")
        descricao = request.form.get("descricao")
        arquivo = request.files.get("arquivo")

        if not titulo:
            flash("O título é obrigatório!", "danger")
            return redirect(url_for("authentication_blueprint.admin_docs"))

        # Se houver arquivo, salva localmente
        if arquivo and arquivo.filename != "":
            allowed_extensions = {".pdf", ".docx", ".doc", ".txt"}
            ext = os.path.splitext(arquivo.filename.lower())[1]
            if ext not in allowed_extensions:
                flash(f"Apenas arquivos {', '.join(allowed_extensions)} são permitidos.", "danger")
                return redirect(url_for("authentication_blueprint.admin_docs"))

            upload_dir = current_app.config["UPLOAD_FOLDER"]
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir)

            filename = secure_filename(f"{uuid.uuid4()}_{arquivo.filename}")
            filepath = os.path.join(upload_dir, filename)
            arquivo.save(filepath)
            
            # Usamos um esquema especial 'file://' para identificar arquivos locais
            url = f"file://{filepath}"

        if not url:
            flash("Você deve fornecer uma URL ou fazer o upload de um arquivo!", "danger")
        else:
            doc = DocumentoOficial(titulo=titulo, url=url, descricao=descricao)
            db.session.add(doc)
            db.session.commit()
            
            # Inicia o processamento RAG imediatamente
            try:
                executar_revisao_documento(doc.id)
                flash("Documento adicionado e enviado para processamento RAG!", "success")
            except Exception as e:
                flash(f"Documento adicionado, mas houve erro no processamento: {e}", "warning")

        return redirect(url_for("authentication_blueprint.admin_docs"))

    documentos = DocumentoOficial.query.order_by(DocumentoOficial.criado_em.desc()).all()
    return render_template("admin/admin-docs.html", documentos=documentos)


@blueprint.route("/admin/docs/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
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


@blueprint.route("/admin/versions")
@login_required
@admin_required
def admin_versions():
    versoes = DocumentoVersao.query.order_by(desc(DocumentoVersao.criado_em)).limit(200).all()
    return render_template("admin/versions.html", versoes=versoes)


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


@blueprint.route("/admin/feedbacks")
@login_required
@admin_required
def admin_feedbacks():
    page = int(request.args.get("page", 1))
    per_page = 50
    stmt = select(ChatFeedback).filter_by(rating="down").order_by(desc(ChatFeedback.updated_at), desc(ChatFeedback.id))
    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    feedbacks = pagination.items
    all_feedbacks = db.session.execute(stmt).scalars().all()
    dashboard = _feedback_dashboard_data(all_feedbacks)
    return render_template(
        "admin/feedbacks.html",
        feedbacks=feedbacks,
        pagination=pagination,
        stats=dashboard["stats"],
        recurrent_failures=dashboard["recurrent_failures"],
        recurring_questions=dashboard["recurring_questions"],
        classify_feedback_failure=_classify_feedback_failure,
    )


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
    doc.sugerido_obsoleto = False
    doc.ativo = False
    db.session.commit()
    flash("Documento marcado como obsoleto definitivamente.", "success")
    return redirect(url_for("authentication_blueprint.admin_docs"))


@blueprint.route("/admin/versions/mark-obsolete/<int:versao_id>", methods=["POST"])
@login_required
@admin_required
def admin_mark_obsolete(versao_id):
    versao = DocumentoVersao.query.get_or_404(versao_id)
    versao.status_processamento = "obsoleto"
    db.session.commit()
    flash("Versão marcada como obsoleta.", "success")
    return redirect(request.referrer or url_for("authentication_blueprint.admin_versions"))


@blueprint.route("/admin/trigger/<string:agente>", methods=["POST"])
@login_required
@admin_required
def admin_trigger_agent(agente):
    log = LogProcessamento(
        versao_id=None,
        agente=agente,
        acao="manual_trigger",
        detalhe=f"Trigger manual pelo usuário {current_user.username}",
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
