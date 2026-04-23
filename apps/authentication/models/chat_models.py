# -*- encoding: utf-8 -*-
"""
Modelos relacionados a conversas, memoria e feedback do chatbot.
"""

from datetime import datetime

from apps import db


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=True)
    thread_id = db.Column(db.String(64), nullable=False)
    sender = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    thoughts = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    feedbacks = db.relationship(
        "ChatFeedback",
        backref="bot_message",
        lazy=True,
        foreign_keys="ChatFeedback.bot_message_id",
    )

    def __repr__(self):
        return f"<ChatMessage {self.id} {self.sender}>"


class UserMemory(db.Model):
    __tablename__ = "user_memories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=True)
    thread_id = db.Column(db.String(64), nullable=True)
    memory_key = db.Column(db.String(64), nullable=False)
    memory_value = db.Column(db.Text, nullable=False)
    source_message_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"), nullable=True)
    confidence = db.Column(db.Float, default=1.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserMemory {self.memory_key}={self.memory_value[:20]}>"


class ChatFeedback(db.Model):
    __tablename__ = "chat_feedbacks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("Users.id"), nullable=True)
    thread_id = db.Column(db.String(64), nullable=False)
    user_message_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"), nullable=True)
    bot_message_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    rating = db.Column(db.String(10), nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ChatFeedback {self.id} {self.rating}>"
