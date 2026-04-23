import uuid

from flask import jsonify

from apps.core import blueprint
from apps.core.chat.services.conversation_service import delete_conversation, list_conversations
from apps.core.chat.services.session_service import register_thread_id


@blueprint.route("/chatbot/conversations", methods=["GET"])
def chatbot_conversations():
    return jsonify(list_conversations())


@blueprint.route("/chatbot/conversations", methods=["POST"])
def chatbot_new_conversation():
    thread_id = register_thread_id(str(uuid.uuid4()))
    return jsonify({"thread_id": thread_id})


@blueprint.route("/chatbot/conversations/<string:thread_id>", methods=["DELETE"])
def chatbot_delete_conversation(thread_id: str):
    payload, status = delete_conversation(thread_id)
    return jsonify(payload), status
