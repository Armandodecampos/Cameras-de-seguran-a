import unittest
from unittest.mock import MagicMock, patch
import os
import json

# Mock customtkinter and other GUI dependencies
import sys
mock_ctk = MagicMock()
sys.modules["customtkinter"] = mock_ctk
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.ImageTk"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["requests.auth"] = MagicMock()

# Mock cv2
mock_cv2 = MagicMock()
sys.modules["cv2"] = mock_cv2

# Mock CentralMonitoramento to test its logic
# We need to inherit from a mock because CentralMonitoramento(ctk.CTk)
class MockCTk:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): pass
    def protocol(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def after(self, *args, **kwargs): pass
    def update_idletasks(self, *args, **kwargs): pass
    def state(self, *args, **kwargs): pass
    def mainloop(self, *args, **kwargs): pass
    def destroy(self, *args, **kwargs): pass
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_width(self): return 1200
    def winfo_height(self): return 800

with patch('customtkinter.CTk', MockCTk):
    from Cameras import CentralMonitoramento

class TestPresets(unittest.TestCase):
    def setUp(self):
        # Prevent file system side effects during init
        with patch('os.path.exists', return_value=False):
            with patch('os.path.expanduser', return_value='/tmp'):
                self.app = CentralMonitoramento()

        # Manually setup what we need
        self.app.presets = {}
        self.app.grid_cameras = ["192.168.1.1"] * 20
        self.app.arquivo_presets = "/tmp/presets_grid_abi.json"
        self.app.ultimo_preset = None

        # Mock UI methods
        self.app.atualizar_lista_presets_ui = MagicMock()
        self.app.salvar_presets = MagicMock()
        self.app.abrir_modal_input = MagicMock()
        self.app.abrir_modal_confirmacao = MagicMock()
        self.app.abrir_modal_alerta = MagicMock()

    def test_salvar_preset_vazio(self):
        # Mock a name being entered in salvar_preset_atual
        self.app.salvar_preset_atual()
        on_name_entered = self.app.abrir_modal_input.call_args[0][2]

        # Test empty string
        on_name_entered("   ")
        self.app.abrir_modal_alerta.assert_called_with("Aviso", "O nome da predefinição não pode ser vazio.")
        self.assertEqual(len(self.app.presets), 0)

    def test_salvar_novo_preset(self):
        self.app.salvar_preset_atual()
        on_name_entered = self.app.abrir_modal_input.call_args[0][2]

        on_name_entered("Preset1")
        self.assertIn("Preset1", self.app.presets)
        self.assertEqual(self.app.presets["Preset1"], ["192.168.1.1"] * 20)
        self.assertEqual(self.app.ultimo_preset, "Preset1")
        self.app.salvar_presets.assert_called()
        self.app.atualizar_lista_presets_ui.assert_called()

    def test_renomear_preset(self):
        self.app.presets = {"Antigo": ["1.1.1.1"] * 20}
        self.app.ultimo_preset = "Antigo"

        self.app.renomear_preset("Antigo")
        on_name_entered = self.app.abrir_modal_input.call_args[0][2]

        # Test rename to empty
        on_name_entered("  ")
        self.app.abrir_modal_alerta.assert_called_with("Aviso", "O nome da predefinição não pode ser vazio.")

        # Test rename to existing
        self.app.presets["Novo"] = ["2.2.2.2"] * 20
        on_name_entered("Novo")
        self.app.abrir_modal_alerta.assert_called_with("Erro", "Já existe uma predefinição com este nome.")

        # Test successful rename
        on_name_entered("Renomeado")
        self.assertIn("Renomeado", self.app.presets)
        self.assertNotIn("Antigo", self.app.presets)
        self.assertEqual(self.app.ultimo_preset, "Renomeado")

    def test_deletar_preset(self):
        self.app.presets = {"Deletar": ["1.1.1.1"] * 20}
        self.app.ultimo_preset = "Deletar"

        self.app.deletar_preset("Deletar")
        callback_sim = self.app.abrir_modal_confirmacao.call_args[0][2]

        callback_sim()
        self.assertNotIn("Deletar", self.app.presets)
        self.assertIsNone(self.app.ultimo_preset)
        self.app.salvar_presets.assert_called()

if __name__ == "__main__":
    unittest.main()
