import os
import sys
import uuid
import unittest
from unittest.mock import patch

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from apps import create_app, db
from apps.config import DebugConfig
from apps.authentication import ChatMessage, UserMemory, ChatFeedback, Users


class TestChatbotRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(DebugConfig)
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        self.thread_id = str(uuid.uuid4())
        with self.client.session_transaction() as sess:
            sess["thread_id"] = self.thread_id
            sess["chat_thread_ids"] = [self.thread_id]

    def tearDown(self):
        with self.app.app_context():
            ChatFeedback.query.filter_by(thread_id=self.thread_id).delete()
            UserMemory.query.filter_by(thread_id=self.thread_id).delete()
            ChatMessage.query.filter_by(thread_id=self.thread_id).delete()
            Users.query.filter(Users.username.like("admin_test_%")).delete()
            db.session.commit()

    def test_post_chatbot_envia_historico_e_memoria(self):
        with self.app.app_context():
            db.session.add(
                ChatMessage(
                    user_id=None,
                    thread_id=self.thread_id,
                    sender="user",
                    content="Meu nome é Larissa",
                )
            )
            db.session.add(
                ChatMessage(
                    user_id=None,
                    thread_id=self.thread_id,
                    sender="bot",
                    content="Prazer, Larissa!",
                )
            )
            db.session.add(
                UserMemory(
                    user_id=None,
                    thread_id=self.thread_id,
                    memory_key="estilo_resposta",
                    memory_value="detalhada",
                )
            )
            db.session.commit()

        with patch("apps.core.run_chatbot") as mock_run_chatbot:
            mock_run_chatbot.return_value = {
                "response": "Resposta de teste",
                "status": "success",
                "answer": "Resposta de teste",
                "sources": [],
                "thoughts": None,
            }
            response = self.client.post(
                "/chatbot",
                json={"thread_id": self.thread_id, "message": "Prefiro respostas objetivas"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_run_chatbot.called)
        _, kwargs = mock_run_chatbot.call_args
        self.assertIn("history", kwargs)
        self.assertEqual(len(kwargs["history"]), 2)
        self.assertIn("Nome: Larissa", kwargs["user_profile"])
        self.assertIn("Estilo de resposta preferido", kwargs["user_profile"])

    def test_feedback_persistido_e_retorno_no_historico(self):
        with self.app.app_context():
            user_message = ChatMessage(
                user_id=None,
                thread_id=self.thread_id,
                sender="user",
                content="Oi, tudo bem?",
            )
            bot_message = ChatMessage(
                user_id=None,
                thread_id=self.thread_id,
                sender="bot",
                content="Tudo bem! Como posso ajudar?",
            )
            db.session.add(user_message)
            db.session.add(bot_message)
            db.session.commit()
            bot_id = bot_message.id

        feedback_response = self.client.post(
            "/chatbot/feedback",
            json={"bot_message_id": bot_id, "rating": "up"},
        )
        self.assertEqual(feedback_response.status_code, 200)

        with self.app.app_context():
            saved = ChatFeedback.query.filter_by(bot_message_id=bot_id).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.rating, "up")

        history_response = self.client.get(f"/chatbot?thread_id={self.thread_id}")
        self.assertEqual(history_response.status_code, 200)
        messages = history_response.json["messages"]
        bot_payload = next(item for item in messages if item["sender"] == "bot")
        self.assertEqual(bot_payload["feedback_rating"], "up")

    def test_feedback_down_gera_resposta_revisada(self):
        with self.app.app_context():
            user_message = ChatMessage(
                user_id=None,
                thread_id=self.thread_id,
                sender="user",
                content="Explique o regimento interno",
            )
            bot_message = ChatMessage(
                user_id=None,
                thread_id=self.thread_id,
                sender="bot",
                content="Não encontrei essa informação.",
            )
            db.session.add(user_message)
            db.session.add(bot_message)
            db.session.commit()
            bot_id = bot_message.id

        with patch("apps.core.melhorar_resposta_com_feedback") as mock_improve:
            mock_improve.return_value = {
                "answer": "O Regimento Interno organiza o funcionamento institucional e define regras de atuação.",
                "sources": [],
                "docs": [],
                "has_rag_context": True,
                "status": "success",
            }
            feedback_response = self.client.post(
                "/chatbot/feedback",
                json={"bot_message_id": bot_id, "rating": "down"},
            )

        self.assertEqual(feedback_response.status_code, 200)
        payload = feedback_response.get_json()
        self.assertIn("revised_response", payload)
        self.assertIn("Resposta revisada", payload["revised_response"])

        with self.app.app_context():
            saved_feedback = ChatFeedback.query.filter_by(bot_message_id=bot_id).first()
            self.assertIsNotNone(saved_feedback)
            self.assertEqual(saved_feedback.rating, "down")
            self.assertIn("Resposta revisada", saved_feedback.comment or "")
            revised_messages = ChatMessage.query.filter_by(thread_id=self.thread_id, sender="bot").all()
            self.assertEqual(len(revised_messages), 2)

    def test_admin_feedbacks_lista_respostas_negativas(self):
        with self.app.app_context():
            admin = Users(
                username=f"admin_test_{uuid.uuid4().hex[:8]}",
                email=f"admin_{uuid.uuid4().hex[:8]}@teste.com",
                password="123456",
                perfil="Administrador",
            )
            db.session.add(admin)
            db.session.flush()
            admin_id = admin.id
            user_message = ChatMessage(
                user_id=None,
                thread_id=self.thread_id,
                sender="user",
                content="O que diz o manual?",
            )
            bot_message = ChatMessage(
                user_id=None,
                thread_id=self.thread_id,
                sender="bot",
                content="Resposta curta",
                thoughts='{"decision": {"route": "tavily_web", "rag_status": "not_found"}}',
            )
            db.session.add(user_message)
            db.session.add(bot_message)
            db.session.flush()
            db.session.add(
                ChatFeedback(
                    user_id=admin_id,
                    thread_id=self.thread_id,
                    user_message_id=user_message.id,
                    bot_message_id=bot_message.id,
                    question=user_message.content,
                    answer=bot_message.content,
                    rating="down",
                    comment="**Resposta revisada**\n\nResposta ampliada.",
                )
            )
            db.session.commit()

            with self.client.session_transaction() as sess:
                sess["_user_id"] = str(admin_id)
                sess["_fresh"] = True

        response = self.client.get("/admin/feedbacks")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Feedbacks Negativos", response.get_data(as_text=True))
        self.assertIn("O que diz o manual?", response.get_data(as_text=True))

    def test_delete_conversation_remove_dependencias_relacionadas(self):
        with self.app.app_context():
            user_message = ChatMessage(
                user_id=None,
                thread_id=self.thread_id,
                sender="user",
                content="Meu nome é Larissa",
            )
            bot_message = ChatMessage(
                user_id=None,
                thread_id=self.thread_id,
                sender="bot",
                content="Olá, Larissa!",
            )
            db.session.add(user_message)
            db.session.add(bot_message)
            db.session.flush()

            db.session.add(
                UserMemory(
                    user_id=None,
                    thread_id=self.thread_id,
                    memory_key="nome",
                    memory_value="Larissa",
                    source_message_id=user_message.id,
                )
            )
            db.session.add(
                ChatFeedback(
                    user_id=None,
                    thread_id=self.thread_id,
                    user_message_id=user_message.id,
                    bot_message_id=bot_message.id,
                    question=user_message.content,
                    answer=bot_message.content,
                    rating="down",
                    comment="**Resposta revisada**\n\nTeste.",
                )
            )
            db.session.commit()

        response = self.client.delete(f"/chatbot/conversations/{self.thread_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["deleted"])

        with self.app.app_context():
            self.assertEqual(ChatMessage.query.filter_by(thread_id=self.thread_id).count(), 0)
            self.assertEqual(ChatFeedback.query.filter_by(thread_id=self.thread_id).count(), 0)
            self.assertEqual(UserMemory.query.filter_by(thread_id=self.thread_id).count(), 0)


if __name__ == "__main__":
    unittest.main()
