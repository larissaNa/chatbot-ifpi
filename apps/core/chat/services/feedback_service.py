from flask_login import current_user

from apps import db
from apps.authentication import ChatFeedback, ChatMessage
from .conversation_service import base_chat_query, chat_history_limit, get_recent_thread_messages
from .memory_service import build_effective_user_profile
from .serialization_service import format_conversation_context


def submit_feedback(*, bot_message_id: int, rating: str, improve_response) -> tuple[dict, int]:
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

    feedback = ChatFeedback.query.filter_by(bot_message_id=bot_message.id).first()
    if feedback:
        feedback.rating = rating
        feedback.question = user_message.content if user_message else ""
        feedback.answer = bot_message.content or ""
    else:
        feedback = ChatFeedback(
            user_id=current_user.id if current_user.is_authenticated else None,
            thread_id=bot_message.thread_id,
            user_message_id=user_message.id if user_message else None,
            bot_message_id=bot_message.id,
            question=user_message.content if user_message else "",
            answer=bot_message.content or "",
            rating=rating,
        )
        db.session.add(feedback)

    response_payload = {"ok": True, "bot_message_id": bot_message.id, "rating": rating}

    if rating == "down":
        history_messages = get_recent_thread_messages(bot_message.thread_id, limit=chat_history_limit())
        user_id = current_user.id if current_user.is_authenticated else None
        _, user_profile, _ = build_effective_user_profile(
            user_id=user_id,
            thread_id=bot_message.thread_id,
            history_messages=history_messages,
        )

        improved = improve_response(
            question=user_message.content if user_message else "",
            previous_answer=bot_message.content or "",
            conversation_context=format_conversation_context(history_messages, limit=chat_history_limit()),
            user_profile=user_profile,
        )
        revised_text = (improved.get("answer") or "").strip()
        if revised_text:
            revised_content = f"**Resposta revisada**\n\n{revised_text}"
            revised_message = ChatMessage(
                user_id=user_id,
                thread_id=bot_message.thread_id,
                sender="bot",
                content=revised_content,
            )
            db.session.add(revised_message)
            feedback.comment = revised_content
            db.session.commit()
            response_payload.update(
                {
                    "revised_response": revised_content,
                    "revised_bot_message_id": revised_message.id,
                    "revised_feedback_rating": None,
                    "revised_has_rag_context": bool(improved.get("has_rag_context")),
                    "revised_sources": improved.get("sources") or [],
                }
            )
            return response_payload, 200

    db.session.commit()
    return response_payload, 200
