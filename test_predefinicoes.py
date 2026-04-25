import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import os
import sys

# Mocking modules before importing CentralMonitoramento
sys.modules['cv2'] = MagicMock()
sys.modules['customtkinter'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageTk'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['requests.auth'] = MagicMock()
sys.modules['mss'] = MagicMock()

import customtkinter as ctk

class FakeCTk:
    def __init__(self, *args, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def protocol(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def after(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): return "1200x800"
    def title(self, *args, **kwargs): pass
    def state(self, *args, **kwargs): pass
    def mainloop(self, *args, **kwargs): pass
    def destroy(self, *args, **kwargs): pass
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_width(self): return 1200
    def winfo_height(self): return 800
    def update_idletasks(self): pass

ctk.CTk = FakeCTk
ctk.set_appearance_mode = MagicMock()

# Now import the class to test
from Cameras import CentralMonitoramento

class TestPredefinicoes(unittest.TestCase):
    @patch('Cameras.CentralMonitoramento.carregar_config', return_value={})
    @patch('Cameras.CentralMonitoramento.carregar_grid', return_value=["0.0.0.0"]*20)
    @patch('Cameras.CentralMonitoramento.carregar_lista_ips', return_value=[])
    @patch('Cameras.CentralMonitoramento.carregar_predefinicoes', return_value={})
    @patch('Cameras.CentralMonitoramento.carregar_posicao_janela')
    @patch('Cameras.CentralMonitoramento.atualizar_lista_cameras_ui')
    @patch('Cameras.CentralMonitoramento.atualizar_lista_predefinicoes_ui')
    @patch('Cameras.CentralMonitoramento.loop_exibicao')
    @patch('threading.Thread')
    def setUp(self, mock_thread, mock_loop, mock_ui_pre, mock_ui_cam, mock_pos, mock_pre, mock_ips, mock_grid, mock_config):
        self.app = CentralMonitoramento()
        self.app.predefinicoes = {}

    def test_salvar_predefinicao(self):
        self.app.grid_cameras = ["192.168.1.1"] + ["0.0.0.0"]*19
        with patch('Cameras.CentralMonitoramento.salvar_predefinicoes'):
            self.app._salvar_predefinicao("Teste")

        self.assertIn("Teste", self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes["Teste"][0], "192.168.1.1")
        self.assertEqual(self.app.ultima_predefinicao, "Teste")

    def test_deletar_predefinicao(self):
        self.app.predefinicoes = {"Teste": ["0.0.0.0"]*20}
        self.app.ultima_predefinicao = "Teste"

        with patch('Cameras.CentralMonitoramento.salvar_predefinicoes'):
            self.app._deletar_predefinicao("Teste")

        self.assertNotIn("Teste", self.app.predefinicoes)
        self.assertIsNone(self.app.ultima_predefinicao)

    def test_renomear_predefinicao(self):
        self.app.predefinicoes = {"Antigo": ["0.0.0.0"]*20}
        self.app.ultima_predefinicao = "Antigo"

        # Simulating the callback from abrir_modal_input
        def mock_modal_input(titulo, msg, callback, valor_inicial=""):
            callback("Novo")

        with patch('Cameras.CentralMonitoramento.abrir_modal_input', side_effect=mock_modal_input):
            with patch('Cameras.CentralMonitoramento.salvar_predefinicoes'):
                self.app.renomear_predefinicao("Antigo")

        self.assertNotIn("Antigo", self.app.predefinicoes)
        self.assertIn("Novo", self.app.predefinicoes)
        self.assertEqual(self.app.ultima_predefinicao, "Novo")

    def test_aplicar_predefinicao(self):
        self.app.predefinicoes = {"Preset1": ["192.168.1.100"] + ["0.0.0.0"]*19}
        self.app.grid_cameras = ["0.0.0.0"]*20

        with patch('Cameras.CentralMonitoramento.atribuir_ip_ao_slot') as mock_atribuir:
            with patch('Cameras.CentralMonitoramento.iniciar_conexao_assincrona'):
                with patch('Cameras.CentralMonitoramento.salvar_grid'):
                    self.app.aplicar_predefinicao("Preset1")

        # Check if it tried to attribute the IP to the first slot
        mock_atribuir.assert_any_call(0, "192.168.1.100", atualizar_ui=False, gerenciar_conexoes=False, salvar=False)
        self.assertEqual(self.app.ultima_predefinicao, "Preset1")

if __name__ == '__main__':
    unittest.main()
