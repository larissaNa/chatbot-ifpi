import unittest
import sys
import os

# Adiciona a raiz ao path para importar 'run'
sys.path.append('/')

from run import app
from apps import db
from apps.authentication import DocumentoOficial

class TestObsolescenceLogic(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        # Usar banco em memória do SQLite para isolamento total
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_fluxo_obsolescencia(self):
        print("\n--- Teste Automatizado de Backend ---")
        # 1. Criação Inicial
        doc = DocumentoOficial(titulo="Doc Teste", url="http://teste.com")
        db.session.add(doc)
        db.session.commit()
        
        self.assertTrue(doc.ativo)
        self.assertFalse(doc.obsoleto)
        
        # 2. Simular Agente Marcando Sugestão
        doc.sugerido_obsoleto = True
        db.session.commit()
        
        doc_recuperado = DocumentoOficial.query.get(doc.id)
        self.assertTrue(doc_recuperado.sugerido_obsoleto)
        self.assertTrue(doc_recuperado.ativo, "Deve continuar ativo até confirmação")
        print("[PASS] Sugestão de obsolescência não desativa o documento.")

        # 3. Simular Admin Confirmando
        doc.obsoleto = True
        doc.sugerido_obsoleto = False
        doc.ativo = False
        db.session.commit()

        doc_final = DocumentoOficial.query.get(doc.id)
        self.assertTrue(doc_final.obsoleto)
        self.assertFalse(doc_final.sugerido_obsoleto)
        self.assertFalse(doc_final.ativo)
        print("[PASS] Confirmação de obsolescência desativa o documento e limpa sugestão.")
        
        print("--- Fim do Teste ---")

if __name__ == '__main__':
    unittest.main()
