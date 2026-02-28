import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import tempfile
import shutil

# 1. Prepare Mocks for GUI Dependencies before importing Cameras
sys.modules['cv2'] = MagicMock()
mock_ctk = MagicMock()
sys.modules['customtkinter'] = mock_ctk

# Mocking necessary CustomTkinter classes
mock_ctk.CTk = MagicMock
mock_ctk.CTkTabview = MagicMock
mock_ctk.CTkFrame = MagicMock
mock_ctk.CTkScrollableFrame = MagicMock
mock_ctk.CTkButton = MagicMock
mock_ctk.CTkLabel = MagicMock
mock_ctk.CTkEntry = MagicMock
mock_ctk.CTkImage = MagicMock

sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageTk'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['requests.auth'] = MagicMock()

from Cameras import CentralMonitoramento

# A simpler approach to avoid Mock attribute issues: bypass inheritance for logic test
class TestPresets(unittest.TestCase):
    def setUp(self):
        # Create a cross-platform temporary directory
        self.test_dir = tempfile.mkdtemp()

        # Patch home directory
        self.expanduser_patcher = patch('os.path.expanduser', return_value=self.test_dir)
        self.expanduser_patcher.start()

        # Create a dummy object and bind the methods manually
        class App:
            pass
        self.app = App()
        self.app.presets = {}
        self.app.grid_cameras = ["0.0.0.0"] * 20
        self.app.ultimo_preset = None
        self.app.preset_widgets = {}
        self.app.BG_SIDEBAR = "#1A1A1A"
        self.app.ACCENT_WINE = "#7B1010"

        # Mock UI-related methods
        self.app.salvar_presets = MagicMock()
        self.app.atualizar_lista_presets_ui = MagicMock()
        self.app.abrir_modal_input = MagicMock()
        self.app.abrir_modal_alerta = MagicMock()
        self.app.abrir_modal_confirmacao = MagicMock()
        self.app.pintar_preset = MagicMock()

        # Bind methods from the real class to our dummy object
        self.app.salvar_preset_atual = CentralMonitoramento.salvar_preset_atual.__get__(self.app)
        self.app._salvar_preset = CentralMonitoramento._salvar_preset.__get__(self.app)
        self.app.renomear_preset = CentralMonitoramento.renomear_preset.__get__(self.app)
        self.app._deletar_preset = CentralMonitoramento._deletar_preset.__get__(self.app)

    def tearDown(self):
        self.expanduser_patcher.stop()
        shutil.rmtree(self.test_dir)

    def test_save_preset(self):
        self.app.grid_cameras[0] = "192.168.1.100"
        preset_name = "New Preset"
        self.app._salvar_preset(preset_name)
        self.assertIn(preset_name, self.app.presets)
        self.assertEqual(self.app.presets[preset_name][0], "192.168.1.100")
        self.assertEqual(self.app.ultimo_preset, preset_name)
        self.app.salvar_presets.assert_called_once()

    def test_rename_preset(self):
        self.app.presets = {"Old": ["1.1.1.1"] * 20}
        self.app.ultimo_preset = "Old"
        self.app.abrir_modal_input.side_effect = lambda t, m, cb, valor_inicial=None: cb("  New  ")
        self.app.renomear_preset("Old")
        self.assertNotIn("Old", self.app.presets)
        self.assertIn("New", self.app.presets)
        self.assertEqual(self.app.ultimo_preset, "New")

    def test_delete_preset(self):
        self.app.presets = {"Trash": ["0.0.0.0"] * 20}
        self.app.ultimo_preset = "Trash"
        self.app._deletar_preset("Trash")
        self.assertNotIn("Trash", self.app.presets)
        self.assertIsNone(self.app.ultimo_preset)

    def test_empty_name_validation(self):
        self.app.abrir_modal_input.side_effect = lambda t, m, cb, valor_inicial=None: cb("   ")
        self.app.salvar_preset_atual()
        self.app.abrir_modal_alerta.assert_called_with("Aviso", "O nome da predefinição não pode estar vazio.")
        self.assertEqual(len(self.app.presets), 0)

        self.app.abrir_modal_alerta.reset_mock()
        self.app.renomear_preset("SomeName")
        self.app.abrir_modal_alerta.assert_called_with("Aviso", "O nome da predefinição não pode estar vazio.")

if __name__ == '__main__':
    unittest.main()
