import unittest
from unittest.mock import MagicMock, patch
import os
import json
import sys

# Mocking customtkinter and other GUI-related modules before importing CentralMonitoramento
sys.modules['customtkinter'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageTk'] = MagicMock()
sys.modules['cv2'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['requests.auth'] = MagicMock()

import customtkinter as ctk

# We need CentralMonitoramento to be importable.
# Since CentralMonitoramento inherits from ctk.CTk, we need to make sure the mock allows inheritance.
class FakeCTk:
    def __init__(self, *args, **kwargs):
        pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def protocol(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def after(self, *args, **kwargs): pass
    def title(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): pass
    def state(self, *args, **kwargs): pass
    def update_idletasks(self, *args, **kwargs): pass
    def destroy(self, *args, **kwargs): pass
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_width(self): return 1200
    def winfo_height(self): return 800

ctk.CTk = FakeCTk
ctk.set_appearance_mode = MagicMock()

from Cameras import CentralMonitoramento

class TestPredefinicoes(unittest.TestCase):
    def setUp(self):
        # Patching file paths to avoid touching real config files
        self.patcher_expanduser = patch('os.path.expanduser', return_value='/tmp')
        self.mock_expanduser = self.patcher_expanduser.start()

        # Patching os.path.exists to control file loading
        self.patcher_exists = patch('os.path.exists', return_value=False)
        self.mock_exists = self.patcher_exists.start()

        # Patching open to avoid real file I/O
        self.patcher_open = patch('builtins.open', unittest.mock.mock_open())
        self.mock_open = self.patcher_open.start()

        # Initialize the app
        with patch('threading.Thread'): # Avoid starting worker threads
            self.app = CentralMonitoramento()

        # Initialize some test data
        self.app.predefinicoes = {
            "Pre1": ["1.1.1.1"] * 20,
            "Pre2": ["2.2.2.2"] * 20
        }
        self.app.grid_cameras = ["0.0.0.0"] * 20

    def tearDown(self):
        self.patcher_expanduser.stop()
        self.patcher_exists.stop()
        self.patcher_open.stop()

    def test_salvar_predefinicao(self):
        nome = "NovaPre"
        self.app.grid_cameras = ["3.3.3.3"] * 20
        self.app._salvar_predefinicao(nome)

        self.assertIn(nome, self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes[nome], ["3.3.3.3"] * 20)
        self.assertEqual(self.app.ultima_predefinicao, nome)

    def test_aplicar_predefinicao(self):
        nome = "Pre1"
        # Mocking necessary methods called by aplicar_predefinicao
        self.app.pintar_predefinicao = MagicMock()
        self.app.atribuir_ip_ao_slot = MagicMock()
        self.app.salvar_grid = MagicMock()
        self.app.iniciar_conexao_assincrona = MagicMock()
        self.app.selecionar_slot = MagicMock()

        self.app.fila_pendente_conexoes.put(("old_ip", 102))
        self.app.ips_em_fila.add("old_ip")
        self.app.camera_handlers["connecting_ip"] = "CONECTANDO"

        self.app.aplicar_predefinicao(nome)

        # Verify cleaning logic
        self.assertTrue(self.app.fila_pendente_conexoes.empty())
        self.assertEqual(len(self.app.ips_em_fila), 0)
        self.assertNotIn("connecting_ip", self.app.camera_handlers)

        # Verify application logic
        self.assertEqual(self.app.ultima_predefinicao, nome)
        self.app.atribuir_ip_ao_slot.assert_called()
        self.app.iniciar_conexao_assincrona.assert_called_with("1.1.1.1", 102)

    def test_deletar_predefinicao(self):
        nome = "Pre1"
        self.app.ultima_predefinicao = nome
        self.app._deletar_predefinicao(nome)

        self.assertNotIn(nome, self.app.predefinicoes)
        self.assertIsNone(self.app.ultima_predefinicao)

    def test_pos_conexao_robustness(self):
        ip = "9.9.9.9"
        mock_handler = MagicMock()

        # Scenario 1: IP still in grid
        self.app.grid_cameras[0] = ip
        self.app._pos_conexao(True, mock_handler, ip)
        self.assertEqual(self.app.camera_handlers[ip], mock_handler)

        # Scenario 2: IP no longer in grid
        ip2 = "8.8.8.8"
        mock_handler2 = MagicMock()
        self.app.grid_cameras = ["0.0.0.0"] * 20 # Remove all
        self.app._pos_conexao(True, mock_handler2, ip2)
        self.assertNotIn(ip2, self.app.camera_handlers)
        mock_handler2.parar.assert_called_once()

if __name__ == '__main__':
    unittest.main()
