from flask import Blueprint, request, jsonify, render_template
from apps.reports.orchestrator import run_chatbot

blueprint = Blueprint("reports", __name__)

@blueprint.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "POST":
        user_input = request.json.get("message", "")
        if not user_input:
            return jsonify({"error": "Mensagem não fornecida."}), 400

        response = run_chatbot(user_input)
        return jsonify({"response": response})

    return render_template("chatbot.html")  # se for GET
