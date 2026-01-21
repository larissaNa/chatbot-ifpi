import unittest
from run import app
from apps import db
from apps.authentication.models import DocumentoOficial

class TestObsolescenceLogic(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Banco em memória para teste rápido
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_fluxo_obsolescencia(self):
        # 1. Criação Inicial
        doc = DocumentoOficial(titulo="Doc Teste", url="http://teste.com")
        db.session.add(doc)
        db.session.commit()
        
        self.assertTrue(doc.ativo)
        self.assertFalse(doc.obsoleto)
        self.assertFalse(doc.sugerido_obsoleto)
        
        # 2. Simular Agente Marcando Sugestão
        doc.sugerido_obsoleto = True
        db.session.commit()
        
        doc_recuperado = DocumentoOficial.query.get(doc.id)
        self.assertTrue(doc_recuperado.sugerido_obsoleto)
        self.assertTrue(doc_recuperado.ativo, "Deve continuar ativo até confirmação")

        # 3. Simular Admin Confirmando
        doc.obsoleto = True
        doc.sugerido_obsoleto = False
        doc.ativo = False
        db.session.commit()

        doc_final = DocumentoOficial.query.get(doc.id)
        self.assertTrue(doc_final.obsoleto)
        self.assertFalse(doc_final.sugerido_obsoleto)
        self.assertFalse(doc_final.ativo)
        
        print("\n[SUCESSO] Fluxo de obsolescência validado no banco de dados.")

if __name__ == '__main__':
    unittest.main()
