from flask import Flask

from .mail_controller import mail_bp
from .mailboxes_controller import mailboxes_bp
from .member_controller import member_bp
from .session_controller import session_bp
from .teams_controller import teams_bp
from .users_controller import users_bp


def register_phase1_blueprints(app: Flask) -> None:
    app.register_blueprint(session_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(mailboxes_bp)
    app.register_blueprint(mail_bp)
    app.register_blueprint(member_bp)
