from datetime import datetime
from apps import db

class Relatorio(db.Model):
    __tablename__ = "relatorios"

    id               = db.Column(db.Integer, primary_key=True)
    usuario_id       = db.Column(db.Integer, db.ForeignKey("Users.id"),   nullable=False)
    consulta_id      = db.Column(db.Integer, db.ForeignKey("consulta_social.id"), nullable=False)
    conteudo_base64  = db.Column(db.Text,    nullable=False)
    criado_em        = db.Column(db.DateTime, default=datetime.utcnow)

    usuario  = db.relationship("Users",     backref="relatorios")
    consulta = db.relationship("ConsultaSocial", backref="relatorios")
