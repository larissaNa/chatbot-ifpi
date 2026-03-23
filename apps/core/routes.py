from flask import Blueprint, request, jsonify, render_template, session
from flask_login import current_user
from apps.core.main import run_chatbot
from apps import db
from apps.authentication.models import ChatMessage
import uuid

blueprint = Blueprint("core", __name__)


@blueprint.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "POST":
        try:
            user_input = request.json.get("message", "")
            if not user_input:
                return jsonify({"error": "Mensagem não fornecida."}), 400

            if "thread_id" not in session:
                session["thread_id"] = str(uuid.uuid4())

            thread_id = session["thread_id"]
            response = run_chatbot(user_input, thread_id=thread_id)

            user_id = current_user.id if current_user.is_authenticated else None

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

            return jsonify(response)
        except Exception as e:
            import traceback

            traceback.print_exc()
            db.session.rollback()
            return (
                jsonify({"error": "Erro interno."}),
                500,
            )

    thread_id = session.get("thread_id")
    query = ChatMessage.query

    if current_user.is_authenticated:
        query = query.filter_by(user_id=current_user.id)
    elif thread_id:
        query = query.filter_by(thread_id=thread_id)
    else:
        return jsonify({"messages": []})

    messages = query.order_by(ChatMessage.created_at.asc()).all()
    history = [
        {
            "sender": m.sender,
            "content": m.content,
            "thoughts": m.thoughts,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

    return jsonify({"messages": history})
