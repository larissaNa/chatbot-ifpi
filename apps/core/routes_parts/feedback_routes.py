from flask import jsonify, request

from apps.core import blueprint
from apps.core.chat.services.feedback_service import submit_feedback


def _get_improve_callable():
    import apps.core as public_core

    return public_core.melhorar_resposta_com_feedback


@blueprint.route("/chatbot/feedback", methods=["POST"])
def chatbot_feedback():
    payload = request.get_json(silent=True) or {}
    rating = str(payload.get("rating") or "").strip().lower()
    bot_message_id = payload.get("bot_message_id")

    try:
        bot_message_id = int(bot_message_id)
    except Exception:
        return jsonify({"error": "Mensagem inválida."}), 400

    response_payload, status = submit_feedback(
        bot_message_id=bot_message_id,
        rating=rating,
        improve_response=_get_improve_callable(),
    )
    return jsonify(response_payload), status
