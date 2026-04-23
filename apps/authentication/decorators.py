from functools import wraps

from flask import flash, redirect, url_for
from flask_login import current_user


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Acesso não autorizado.", "danger")
            return redirect(url_for("home_blueprint.index"))
        return func(*args, **kwargs)

    return decorated_view
