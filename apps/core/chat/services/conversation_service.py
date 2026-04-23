from flask import current_app, session
from flask_login import current_user

from apps import db
from apps.authentication import ChatFeedback, ChatMessage, UserMemory
from .serialization_service import build_conversation_summaries
from .session_service import get_allowed_thread_ids, remove_session_thread_id


def base_chat_query():
    query = ChatMessage.query
    if current_user.is_authenticated:
        return query.filter_by(user_id=current_user.id)

    allowed_thread_ids = get_allowed_thread_ids() or []
    if not allowed_thread_ids:
        return None
    return query.filter(ChatMessage.thread_id.in_(allowed_thread_ids))


def chat_history_limit() -> int:
    try:
        return int(current_app.config.get("CHAT_HISTORY_LIMIT", 12))
    except Exception:
        return 12


def get_recent_thread_messages(thread_id: str, *, limit: int | None = None) -> list[ChatMessage]:
    if not thread_id:
        return []

    query = base_chat_query()
    if query is None:
        return []

    items = (
        query.filter_by(thread_id=thread_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(limit or chat_history_limit())
        .all()
    )
    items.reverse()
    return items


def list_conversations() -> dict:
    active_thread_id = session.get("thread_id")
    query = base_chat_query()
    if query is None:
        return {"conversations": [], "active_thread_id": active_thread_id}

    messages = query.order_by(ChatMessage.created_at.asc()).all()
    conversations = build_conversation_summaries(messages, active_thread_id)
    return {"conversations": conversations, "active_thread_id": active_thread_id}


def delete_conversation(thread_id: str) -> tuple[dict, int]:
    thread_id = str(thread_id or "").strip()
    if not thread_id:
        return {"error": "Conversa inválida."}, 400

    query = base_chat_query()
    if query is None:
        remove_session_thread_id(thread_id)
        return {"deleted": False, "active_thread_id": session.get("thread_id")}, 200

    try:
        messages = query.filter_by(thread_id=thread_id).all()
        message_ids = [message.id for message in messages if message.id]

        if message_ids:
            ChatFeedback.query.filter(
                (ChatFeedback.thread_id == thread_id)
                | (ChatFeedback.bot_message_id.in_(message_ids))
                | (ChatFeedback.user_message_id.in_(message_ids))
            ).delete(synchronize_session=False)

            UserMemory.query.filter(
                (UserMemory.thread_id == thread_id)
                | (UserMemory.source_message_id.in_(message_ids))
            ).delete(synchronize_session=False)

        for message in messages:
            db.session.delete(message)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return {"error": "Erro ao apagar conversa."}, 500

    remove_session_thread_id(thread_id)
    return {
        "deleted": True,
        "thread_id": thread_id,
        "active_thread_id": session.get("thread_id"),
    }, 200
