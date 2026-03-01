import unittest
from unittest.mock import MagicMock, patch
import json
import os
import tempfile
import sys

# Mock GUI dependencies with real-ish classes to allow inheritance
class MockCTk:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def protocol(self, *args): pass
    def bind(self, *args): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def after(self, *args): pass
    def mainloop(self): pass
    def update_idletasks(self): pass

class MockCTkFrame:
    def __init__(self, *args, **kwargs): pass
    def grid(self, *args, **kwargs): pass
    def pack(self, *args, **kwargs): pass
    def pack_propagate(self, *args): pass
    def winfo_children(self): return []

mock_ctk = MagicMock()
mock_ctk.CTk = MockCTk
mock_ctk.CTkFrame = MockCTkFrame
mock_ctk.set_appearance_mode = MagicMock()
sys.modules['customtkinter'] = mock_ctk

sys.modules['cv2'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageTk'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['requests.auth'] = MagicMock()

import Cameras

class TestPresets(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for presets
        self.temp_presets_file = tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8')
        self.temp_presets_file.close()

        # We want to test the actual methods, so we'll use a real instance but bypass __init__
        self.cm = Cameras.CentralMonitoramento.__new__(Cameras.CentralMonitoramento)
        self.cm.arquivo_presets = self.temp_presets_file.name
        self.cm.presets = {}
        self.cm.grid_cameras = ["192.168.1.1"] * 20
        self.cm.ultimo_preset = None
        self.cm.salvar_presets = lambda: Cameras.CentralMonitoramento.salvar_presets(self.cm)
        self.cm.atualizar_lista_presets_ui = MagicMock()
        self.cm.abrir_modal_alerta = MagicMock()
        self.cm.abrir_modal_confirmacao = MagicMock()
        self.cm.abrir_modal_input = MagicMock()

    def tearDown(self):
        if os.path.exists(self.temp_presets_file.name):
            os.remove(self.temp_presets_file.name)

    def test_salvar_preset(self):
        # Test saving a new preset
        Cameras.CentralMonitoramento._salvar_preset(self.cm, "Teste 1")
        self.assertIn("Teste 1", self.cm.presets)
        self.assertEqual(self.cm.presets["Teste 1"], ["192.168.1.1"] * 20)
        self.assertEqual(self.cm.ultimo_preset, "Teste 1")

        # Verify persistence
        with open(self.cm.arquivo_presets, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertIn("Teste 1", data)

    def test_renomear_preset(self):
        # Setup: save a preset first
        Cameras.CentralMonitoramento._salvar_preset(self.cm, "Antigo")

        # Execute renaming logic directly as if on_name_entered was called
        def mock_input(titulo, msg, callback, valor_inicial=""):
            self.on_name_entered = callback

        self.cm.abrir_modal_input = mock_input
        Cameras.CentralMonitoramento.renomear_preset(self.cm, "Antigo")

        # Call the captured callback
        self.on_name_entered(" Novo ") # testing strip

        self.assertNotIn("Antigo", self.cm.presets)
        self.assertIn("Novo", self.cm.presets)
        self.assertEqual(self.cm.ultimo_preset, "Novo")

    def test_deletar_preset(self):
        # Setup
        Cameras.CentralMonitoramento._salvar_preset(self.cm, "ParaDeletar")

        # Execute deletion
        Cameras.CentralMonitoramento._deletar_preset(self.cm, "ParaDeletar")

        self.assertNotIn("ParaDeletar", self.cm.presets)
        self.assertIsNone(self.cm.ultimo_preset)

    def test_validacao_nome_vazio_salvar(self):
        def mock_input(titulo, msg, callback, valor_inicial=""):
            self.on_name_entered = callback

        self.cm.abrir_modal_input = mock_input
        Cameras.CentralMonitoramento.salvar_preset_atual(self.cm)

        self.on_name_entered("   ") # all spaces

        self.cm.abrir_modal_alerta.assert_called_with("Aviso", "O nome da predefinição não pode estar vazio.")
        self.assertNotIn("   ", self.cm.presets)

    def test_validacao_nome_vazio_renomear(self):
        Cameras.CentralMonitoramento._salvar_preset(self.cm, "Antigo")
        def mock_input(titulo, msg, callback, valor_inicial=""):
            self.on_name_entered = callback

        self.cm.abrir_modal_input = mock_input
        Cameras.CentralMonitoramento.renomear_preset(self.cm, "Antigo")

        self.on_name_entered("   ")

        self.cm.abrir_modal_alerta.assert_called_with("Aviso", "O nome da predefinição não pode estar vazio.")
        self.assertIn("Antigo", self.cm.presets)

if __name__ == '__main__':
    unittest.main()
