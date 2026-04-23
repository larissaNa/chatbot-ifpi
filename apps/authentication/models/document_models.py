# -*- encoding: utf-8 -*-
"""
Modelos relacionados a documentos oficiais, indexacao e logs.
"""

from datetime import datetime

from apps import db


class DocumentoOficial(db.Model):
    __tablename__ = "documentos_oficiais"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    descricao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    obsoleto = db.Column(db.Boolean, default=False)
    sugerido_obsoleto = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    ultima_verificacao = db.Column(db.DateTime)
    ultimo_status_http = db.Column(db.Integer)

    versoes = db.relationship("DocumentoVersao", backref="documento", lazy=True)

    def __repr__(self):
        return f"<DocumentoOficial {self.titulo}>"


class DocumentoVersao(db.Model):
    __tablename__ = "documento_versoes"

    id = db.Column(db.Integer, primary_key=True)
    documento_id = db.Column(
        db.Integer, db.ForeignKey("documentos_oficiais.id"), nullable=False
    )
    versao_numero = db.Column(db.Integer, nullable=False)
    url_arquivo = db.Column(db.String(500))
    hash_conteudo = db.Column(db.String(128))
    status_processamento = db.Column(db.String(32))
    chroma_document_id = db.Column(db.String(255))

    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    processado_em = db.Column(db.DateTime)
    indexado_em = db.Column(db.DateTime)

    chroma_chunks = db.relationship("ChromaIndexRecord", backref="versao", lazy=True)

    def __repr__(self):
        return f"<DocumentoVersao {self.id} Doc={self.documento_id}>"


class ChromaIndexRecord(db.Model):
    __tablename__ = "chroma_index_records"

    id = db.Column(db.Integer, primary_key=True)
    versao_id = db.Column(
        db.Integer, db.ForeignKey("documento_versoes.id"), nullable=False
    )
    chroma_document_id = db.Column(db.String(255))
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ChromaIndex {self.chroma_document_id}>"


class LogProcessamento(db.Model):
    __tablename__ = "logs_processamento"

    id = db.Column(db.Integer, primary_key=True)
    versao_id = db.Column(
        db.Integer, db.ForeignKey("documento_versoes.id"), nullable=True
    )
    agente = db.Column(db.String(64))
    acao = db.Column(db.String(64))
    detalhe = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    documento_id = db.Column(
        db.Integer, db.ForeignKey("documentos_oficiais.id"), nullable=True
    )

    def __repr__(self):
        return f"<Log {self.id} {self.acao}>"
