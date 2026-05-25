# -*- encoding: utf-8 -*-
"""
Rotas administrativas relacionadas a documentos, versoes, logs e feedbacks.
"""

import re
import os
import json
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
    ChatMessage,
    DocumentoOficial,
    DocumentoVersao,
    LogProcessamento,
    UserMemory,
)
from apps.core.documents.services.revision_orchestrator import executar_revisao_documento
from apps.core.chat.services.serialization_service import build_conversation_summaries


def _normalize_feedback_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _parse_feedback_comment(feedback: ChatFeedback) -> dict:
    """Extrai user_comment e conversation_history do campo comment (JSON)."""
    raw = (feedback.comment or "").strip()
    if not raw:
        return {"user_comment": "", "conversation_history": ""}
    try:
        data = json.loads(raw)
        return {
            "user_comment": str(data.get("user_comment") or ""),
            "conversation_history": str(data.get("conversation_history") or ""),
        }
    except Exception:
        # Formato legado (texto puro da resposta revisada)
        return {"user_comment": "", "conversation_history": raw}


def _classify_feedback_failure(feedback: ChatFeedback) -> str:
    answer = _normalize_feedback_text(feedback.answer)
    thoughts = _normalize_feedback_text(getattr(getattr(feedback, "bot_message", None), "thoughts", ""))
    parsed = _parse_feedback_comment(feedback)
    user_comment = _normalize_feedback_text(parsed["user_comment"])

    if not answer:
        return "Resposta vazia"
    if user_comment:
        # Classifica pela palavra-chave no comentário do usuário
        if any(w in user_comment for w in ("errado", "incorreto", "errada", "incorreta", "errou")):
            return "Informação incorreta"
        if any(w in user_comment for w in ("não encontrou", "não achou", "não encontrei", "não localizou")):
            return "RAG sem contexto suficiente"
        if any(w in user_comment for w in ("incompleto", "faltou", "faltando", "incompleta")):
            return "Resposta incompleta"
    if "não encontrei" in answer or "não localizei" in answer:
        return "RAG sem contexto suficiente"
    if "tavily_web" in thoughts or '"route": "tavily_web"' in thoughts:
        return "Fallback para web"
    if len(answer) < 140:
        return "Resposta curta ou genérica"
    return "Necessita investigação"


def _feedback_dashboard_data(feedbacks: list[ChatFeedback]) -> dict:
    failure_counts: dict[str, int] = {}
    repeated_questions: dict[str, dict[str, int | str]] = {}
    with_comment_count = 0

    for feedback in feedbacks:
        label = _classify_feedback_failure(feedback)
        failure_counts[label] = failure_counts.get(label, 0) + 1

        parsed = _parse_feedback_comment(feedback)
        if parsed["user_comment"].strip():
            with_comment_count += 1

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
        "with_comment_count": with_comment_count,
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
        parse_feedback_comment=_parse_feedback_comment,
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


@blueprint.route("/admin/conversations")
@login_required
@admin_required
def admin_conversations():
    """Lista todas as conversas de usuários externos (user_id IS NULL)."""
    page = int(request.args.get("page", 1))
    per_page = 30

    # Busca todos os thread_ids distintos de mensagens anônimas, ordenados pela mais recente
    from sqlalchemy import func
    subq = (
        db.session.query(
            ChatMessage.thread_id,
            func.max(ChatMessage.created_at).label("last_at"),
            func.count(ChatMessage.id).label("msg_count"),
        )
        .filter(ChatMessage.user_id.is_(None))
        .group_by(ChatMessage.thread_id)
        .order_by(desc(func.max(ChatMessage.created_at)))
    )

    total_threads = subq.count()
    thread_rows = subq.offset((page - 1) * per_page).limit(per_page).all()

    # Para cada thread, busca a primeira mensagem do usuário (título) e a última mensagem (preview)
    conversations = []
    for row in thread_rows:
        thread_id = row.thread_id
        first_user_msg = (
            ChatMessage.query
            .filter(ChatMessage.thread_id == thread_id, ChatMessage.user_id.is_(None), ChatMessage.sender == "user")
            .order_by(ChatMessage.created_at.asc())
            .first()
        )
        last_msg = (
            ChatMessage.query
            .filter(ChatMessage.thread_id == thread_id, ChatMessage.user_id.is_(None))
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        conversations.append({
            "thread_id": thread_id,
            "title": (first_user_msg.content or "").strip()[:70] if first_user_msg else "Conversa sem mensagens",
            "last_preview": (last_msg.content or "").strip()[:100] if last_msg else "",
            "last_sender": last_msg.sender if last_msg else "",
            "last_at": row.last_at,
            "msg_count": row.msg_count,
        })

    # Paginação simples
    total_pages = max(1, (total_threads + per_page - 1) // per_page)

    return render_template(
        "admin/conversations.html",
        conversations=conversations,
        page=page,
        total_pages=total_pages,
        total_threads=total_threads,
    )


@blueprint.route("/admin/conversations/<thread_id>")
@login_required
@admin_required
def admin_conversation_detail(thread_id):
    """Exibe todas as mensagens de uma conversa externa específica."""
    messages = (
        ChatMessage.query
        .filter(ChatMessage.thread_id == thread_id, ChatMessage.user_id.is_(None))
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    if not messages:
        flash("Conversa não encontrada ou pertence a um usuário autenticado.", "warning")
        return redirect(url_for("authentication_blueprint.admin_conversations"))

    first_user_msg = next((m for m in messages if m.sender == "user"), None)
    title = (first_user_msg.content or "").strip()[:70] if first_user_msg else thread_id

    return render_template(
        "admin/conversation_detail.html",
        messages=messages,
        thread_id=thread_id,
        title=title,
    )


@blueprint.route("/admin/conversations/<thread_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_conversation_delete(thread_id):
    """Apaga todos os registros de uma conversa externa."""
    UserMemory.query.filter_by(thread_id=thread_id).delete()
    ChatFeedback.query.filter_by(thread_id=thread_id).delete()
    ChatMessage.query.filter(
        ChatMessage.thread_id == thread_id,
        ChatMessage.user_id.is_(None),
    ).delete()
    db.session.commit()
    flash("Conversa apagada com sucesso.", "success")
    return redirect(url_for("authentication_blueprint.admin_conversations"))


@blueprint.route("/admin/conversations/<thread_id>/print")
@login_required
@admin_required
def admin_conversation_print(thread_id):
    """Versão para impressão/PDF de uma conversa."""
    messages = (
        ChatMessage.query
        .filter(ChatMessage.thread_id == thread_id, ChatMessage.user_id.is_(None))
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    if not messages:
        flash("Conversa não encontrada.", "warning")
        return redirect(url_for("authentication_blueprint.admin_conversations"))

    first_user_msg = next((m for m in messages if m.sender == "user"), None)
    title = (first_user_msg.content or "").strip()[:70] if first_user_msg else thread_id

    return render_template(
        "admin/conversation_print.html",
        messages=messages,
        thread_id=thread_id,
        title=title,
    )


@blueprint.route("/admin/system-logs")
@login_required
@admin_required
def admin_system_logs():
    """Visualizador de logs do sistema em tempo real."""
    from apps.core.log_buffer import get_lines
    lines = get_lines(500)
    return render_template("admin/system_logs.html", lines=lines)


@blueprint.route("/admin/system-logs/data")
@login_required
@admin_required
def admin_system_logs_data():
    """Endpoint JSON com as últimas linhas de log (para auto-refresh via fetch)."""
    from flask import jsonify
    from apps.core.log_buffer import get_lines
    n = min(int(request.args.get("n", 500)), 2000)
    return jsonify({"lines": get_lines(n)})


@blueprint.route("/admin/system-logs/export")
@login_required
@admin_required
def admin_system_logs_export():
    """Exporta os logs como arquivo .txt."""
    from flask import Response
    from apps.core.log_buffer import get_lines
    content = "\n".join(get_lines(2000))
    return Response(
        content,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=sistema_logs.txt"},
    )
