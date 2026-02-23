from flask import Flask

from .health_controller import health_bp
from .identity_controller import identity_bp
from .ocr_controller import ocr_bp
from .internal_jobs_controller import internal_jobs_bp
from .mail_controller import mail_bp
from .mail_requests_controller import mail_requests_bp
from .mailboxes_controller import mailboxes_bp
from .member_controller import member_bp
from .notifications_controller import notifications_bp
from .session_controller import session_bp
from .teams_controller import teams_bp
from .users_controller import users_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(ocr_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(mailboxes_bp)
    app.register_blueprint(mail_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(mail_requests_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(internal_jobs_bp)
    app.register_blueprint(identity_bp)


register_phase1_blueprints = register_blueprints
