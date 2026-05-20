from flask import jsonify, request

from apps.core import blueprint
from apps.core.chat.services.feedback_service import submit_feedback


@blueprint.route("/chatbot/feedback", methods=["POST"])
def chatbot_feedback():
    payload = request.get_json(silent=True) or {}
    rating = str(payload.get("rating") or "").strip().lower()
    bot_message_id = payload.get("bot_message_id")
    user_comment = str(payload.get("user_comment") or "").strip()

    try:
        bot_message_id = int(bot_message_id)
    except Exception:
        return jsonify({"error": "Mensagem inválida."}), 400

    response_payload, status = submit_feedback(
        bot_message_id=bot_message_id,
        rating=rating,
        user_comment=user_comment,
    )
    return jsonify(response_payload), status
