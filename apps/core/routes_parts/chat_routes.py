import uuid

from flask import jsonify, request, session
from flask_login import current_user

from apps import db
from apps.authentication import ChatMessage
from apps.core import blueprint
from apps.core.chat.services.conversation_service import base_chat_query, chat_history_limit, get_recent_thread_messages
from apps.core.chat.services.memory_service import build_effective_user_profile, persist_user_memories
from apps.core.chat.services.serialization_service import feedback_map_for_messages, serialize_history_payload, serialize_message
from apps.core.chat.services.session_service import register_thread_id


def _get_run_chatbot():
    import apps.core as public_core

    return public_core.run_chatbot


@blueprint.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "POST":
        try:
            payload = request.get_json(silent=True) or {}
            user_input = payload.get("message", "")
            if not user_input:
                return jsonify({"error": "Mensagem não fornecida."}), 400

            requested_thread_id = str(payload.get("thread_id") or "").strip()
            thread_id = register_thread_id(requested_thread_id or session.get("thread_id") or str(uuid.uuid4()))
            user_id = current_user.id if current_user.is_authenticated else None
            history_messages = get_recent_thread_messages(thread_id, limit=chat_history_limit())
            _, user_profile, current_message_memories = build_effective_user_profile(
                user_id=user_id,
                thread_id=thread_id,
                history_messages=history_messages,
                current_user_input=user_input,
            )

            response = _get_run_chatbot()(
                user_input,
                thread_id=thread_id,
                history=serialize_history_payload(history_messages),
                user_profile=user_profile,
            )

            user_message = ChatMessage(
                user_id=user_id,
                thread_id=thread_id,
                sender="user",
                content=user_input,
            )
            bot_message = ChatMessage(
                user_id=user_id,
                thread_id=thread_id,
                sender="bot",
                content=response.get("response", "") or "",
                thoughts=response.get("thoughts") or None,
            )

            db.session.add(user_message)
            db.session.add(bot_message)
            db.session.commit()
            persist_user_memories(
                user_id=user_id,
                thread_id=thread_id,
                source_message_id=user_message.id,
                memory_candidates=current_message_memories,
            )

            response["thread_id"] = thread_id
            response["bot_message_id"] = bot_message.id
            response["feedback_rating"] = None
            return jsonify(response)
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Erro interno."}), 500

    requested_thread_id = str(request.args.get("thread_id") or "").strip()
    thread_id = register_thread_id(requested_thread_id) if requested_thread_id else session.get("thread_id")
    if not thread_id:
        return jsonify({"messages": []})

    query = base_chat_query()
    if query is None:
        return jsonify({"messages": [], "thread_id": thread_id})

    messages = query.filter_by(thread_id=thread_id).order_by(ChatMessage.created_at.asc()).all()
    feedback_map = feedback_map_for_messages(messages)
    history = [serialize_message(message, feedback_map=feedback_map) for message in messages]

    return jsonify({"messages": history, "thread_id": thread_id})
