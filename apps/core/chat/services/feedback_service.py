import json

from flask_login import current_user

from apps import db
from apps.authentication import ChatFeedback, ChatMessage
from .conversation_service import base_chat_query, chat_history_limit, get_recent_thread_messages
from .memory_service import build_effective_user_profile
from .serialization_service import format_conversation_context


def submit_feedback(*, bot_message_id: int, rating: str, user_comment: str = "") -> tuple[dict, int]:
    rating = str(rating or "").strip().lower()
    if rating not in {"up", "down"}:
        return {"error": "Avaliação inválida."}, 400

    query = base_chat_query()
    if query is None:
        return {"error": "Mensagem não encontrada."}, 404

    bot_message = query.filter(ChatMessage.id == bot_message_id, ChatMessage.sender == "bot").first()
    if not bot_message:
        return {"error": "Mensagem não encontrada."}, 404

    user_message = (
        query.filter(
            ChatMessage.thread_id == bot_message.thread_id,
            ChatMessage.sender == "user",
            ChatMessage.created_at <= bot_message.created_at,
        )
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .first()
    )

    # Captura o histórico completo da thread para diagnóstico
    conversation_history = ""
    if rating == "down":
        history_messages = get_recent_thread_messages(bot_message.thread_id, limit=chat_history_limit())
        conversation_history = format_conversation_context(history_messages, limit=chat_history_limit())

    # Monta o payload de diagnóstico salvo em comment (JSON)
    comment_payload = None
    if rating == "down":
        comment_payload = json.dumps(
            {
                "user_comment": user_comment,
                "conversation_history": conversation_history,
            },
            ensure_ascii=False,
        )

    feedback = ChatFeedback.query.filter_by(bot_message_id=bot_message.id).first()
    if feedback:
        feedback.rating = rating
        feedback.question = user_message.content if user_message else ""
        feedback.answer = bot_message.content or ""
        if comment_payload is not None:
            feedback.comment = comment_payload
    else:
        feedback = ChatFeedback(
            user_id=current_user.id if current_user.is_authenticated else None,
            thread_id=bot_message.thread_id,
            user_message_id=user_message.id if user_message else None,
            bot_message_id=bot_message.id,
            question=user_message.content if user_message else "",
            answer=bot_message.content or "",
            rating=rating,
            comment=comment_payload,
        )
        db.session.add(feedback)

    db.session.commit()
    return {"ok": True, "bot_message_id": bot_message.id, "rating": rating}, 200
