import uuid

from flask import session
from flask_login import current_user


def ensure_session_thread_ids() -> list[str]:
    thread_ids = session.get("chat_thread_ids") or []
    if not isinstance(thread_ids, list):
        thread_ids = []
    thread_ids = [str(t).strip() for t in thread_ids if str(t).strip()]
    session["chat_thread_ids"] = thread_ids
    return thread_ids


def register_thread_id(thread_id: str) -> str:
    thread_id = str(thread_id or "").strip() or str(uuid.uuid4())
    thread_ids = ensure_session_thread_ids()
    if thread_id not in thread_ids:
        thread_ids.insert(0, thread_id)
        session["chat_thread_ids"] = thread_ids[:100]
    session["thread_id"] = thread_id
    session.modified = True
    return thread_id


def remove_session_thread_id(thread_id: str) -> None:
    thread_id = str(thread_id or "").strip()
    if not thread_id:
        return

    thread_ids = ensure_session_thread_ids()
    thread_ids = [item for item in thread_ids if item != thread_id]
    session["chat_thread_ids"] = thread_ids

    if session.get("thread_id") == thread_id:
        session["thread_id"] = thread_ids[0] if thread_ids else None

    session.modified = True


def get_allowed_thread_ids() -> list[str] | None:
    if current_user.is_authenticated:
        return None
    return ensure_session_thread_ids()
