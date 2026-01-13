from flask import Blueprint, request, jsonify, render_template, session
from apps.core.main import run_chatbot
import uuid

blueprint = Blueprint("core", __name__)


@blueprint.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "POST":
        try:
            user_input = request.json.get("message", "")
            if not user_input:
                return jsonify({"error": "Mensagem não fornecida."}), 400
            
            # Garante que existe um thread_id na sessão do usuário
            if "thread_id" not in session:
                session["thread_id"] = str(uuid.uuid4())
            
            response = run_chatbot(user_input, thread_id=session["thread_id"])
            return jsonify(response)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

    return render_template("chatbot.html")  # se for GET
