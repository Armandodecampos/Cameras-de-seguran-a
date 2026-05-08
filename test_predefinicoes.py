import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import json

# Mocking modules that might not be available or are GUI-related
import sys
mock_ctk = MagicMock()
mock_cv2 = MagicMock()
mock_pil = MagicMock()
mock_requests = MagicMock()

# Setup FakeCTk to allow inheritance
class FakeCTk:
    def __init__(self, *args, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def protocol(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def after(self, *args, **kwargs): pass
    def update_idletasks(self, *args, **kwargs): pass
    def winfo_ismapped(self, *args, **kwargs): return True
    def state(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): return "1200x800"
    def title(self, *args, **kwargs): pass
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_width(self): return 1200
    def winfo_height(self): return 800
    def destroy(self): pass
    def mainloop(self): pass
    def _get_window_scaling(self): return 1.0

mock_ctk.CTk = FakeCTk
mock_ctk.set_appearance_mode = MagicMock()

sys.modules["customtkinter"] = mock_ctk
sys.modules["cv2"] = mock_cv2
sys.modules["PIL"] = mock_pil
sys.modules["PIL.Image"] = mock_pil
sys.modules["PIL.ImageTk"] = mock_pil
sys.modules["requests"] = mock_requests
sys.modules["requests.auth"] = MagicMock()

# Now import the class to test
from Cameras import CentralMonitoramento

class TestPredefinicoes(unittest.TestCase):
    @patch('Cameras.CentralMonitoramento.carregar_posicao_janela', return_value=None)
    @patch('Cameras.CentralMonitoramento.carregar_predefinicoes', return_value={})
    @patch('Cameras.CentralMonitoramento.carregar_lista_ips', return_value=[])
    @patch('Cameras.CentralMonitoramento.carregar_config', return_value={})
    @patch('Cameras.CentralMonitoramento.carregar_grid', return_value=["0.0.0.0"]*20)
    def setUp(self, m1, m2, m3, m4, m5):
        self.app = CentralMonitoramento()
        self.app.predefinicoes = {}
        self.app.grid_cameras = ["192.168.1.1"] + ["0.0.0.0"]*19

    def test_salvar_predefinicao(self):
        nome = "Teste 1"
        with patch.object(self.app, 'abrir_modal_input') as mock_input:
            # Simula usuário digitando o nome e confirmando
            mock_input.side_effect = lambda tit, msg, cb: cb(nome)
            self.app.salvar_predefinicao_atual()

            self.assertIn(nome, self.app.predefinicoes)
            self.assertEqual(self.app.predefinicoes[nome][0], "192.168.1.1")
            self.assertEqual(self.app.ultima_predefinicao, nome)

    def test_renomear_predefinicao(self):
        self.app.predefinicoes = {"Antigo": ["192.168.1.1"]*20}
        self.app.ultima_predefinicao = "Antigo"

        with patch.object(self.app, 'abrir_modal_input') as mock_input:
            mock_input.side_effect = lambda tit, msg, cb, valor_inicial="": cb("Novo")
            self.app.renomear_predefinicao("Antigo")

            self.assertNotIn("Antigo", self.app.predefinicoes)
            self.assertIn("Novo", self.app.predefinicoes)
            self.assertEqual(self.app.ultima_predefinicao, "Novo")

    def test_deletar_predefinicao(self):
        self.app.predefinicoes = {"ParaDeletar": ["192.168.1.1"]*20}
        self.app.ultima_predefinicao = "ParaDeletar"

        with patch.object(self.app, 'abrir_modal_confirmacao') as mock_conf:
            mock_conf.side_effect = lambda tit, msg, cb_sim: cb_sim()
            self.app.deletar_predefinicao("ParaDeletar")

            self.assertNotIn("ParaDeletar", self.app.predefinicoes)
            self.assertIsNone(self.app.ultima_predefinicao)

    def test_sobrescrever_predefinicao(self):
        self.app.predefinicoes = {"Existente": ["0.0.0.0"]*20}
        self.app.grid_cameras = ["192.168.1.200"] + ["0.0.0.0"]*19

        with patch.object(self.app, 'abrir_modal_confirmacao') as mock_conf:
            mock_conf.side_effect = lambda tit, msg, cb_sim: cb_sim()
            self.app.sobrescrever_predefinicao("Existente")

            self.assertEqual(self.app.predefinicoes["Existente"][0], "192.168.1.200")

    @patch('Cameras.CentralMonitoramento.iniciar_conexao_assincrona')
    def test_aplicar_predefinicao(self, mock_conn):
        self.app.predefinicoes = {"Preset1": ["10.0.0.1"]*20}
        self.app.aplicar_predefinicao("Preset1")

        self.assertEqual(self.app.grid_cameras[0], "10.0.0.1")
        self.assertEqual(self.app.ultima_predefinicao, "Preset1")
        self.assertTrue(mock_conn.called)

if __name__ == "__main__":
    unittest.main()
