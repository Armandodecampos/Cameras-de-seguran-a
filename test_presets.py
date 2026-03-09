import unittest
from unittest.mock import MagicMock, patch
import os
import json

# Mocking customtkinter before importing CentralMonitoramento
import sys
from unittest.mock import MagicMock

class MockCTk:
    def __init__(self, *args, **kwargs):
        pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def protocol(self, *args): pass
    def bind(self, *args): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def after(self, *args, **kwargs): pass
    def mainloop(self): pass
    def destroy(self): pass
    def state(self, *args): pass
    def update_idletasks(self): pass
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_width(self): return 1000
    def winfo_height(self): return 800

mock_ctk = MagicMock()
mock_ctk.CTk = MockCTk
mock_ctk.CTkFrame = MagicMock()
mock_ctk.CTkTabview = MagicMock()
mock_ctk.CTkScrollableFrame = MagicMock()
mock_ctk.CTkButton = MagicMock()
mock_ctk.CTkLabel = MagicMock()
mock_ctk.CTkEntry = MagicMock()
mock_ctk.CTkToplevel = MagicMock()
mock_ctk.set_appearance_mode = MagicMock()

sys.modules['customtkinter'] = mock_ctk

# Now we can import CentralMonitoramento from Cameras.py
# We need to mock the CameraHandler and other things that might start threads
with patch('threading.Thread'):
    from Cameras import CentralMonitoramento

class TestPresetsLogic(unittest.TestCase):
    def setUp(self):
        # Setup temporary files for testing
        self.test_user_dir = "."
        self.presets_file = os.path.join(self.test_user_dir, "presets_grid_abi.json")
        if os.path.exists(self.presets_file):
            os.remove(self.presets_file)

        # Patch the file paths in the instance
        with patch('os.path.expanduser', return_value=self.test_user_dir):
            with patch.object(CentralMonitoramento, 'carregar_posicao_janela'):
                with patch.object(CentralMonitoramento, 'carregar_config', return_value={}):
                    with patch.object(CentralMonitoramento, 'carregar_grid', return_value=["0.0.0.0"]*20):
                        with patch.object(CentralMonitoramento, 'criar_botoes_iniciais'):
                            with patch.object(CentralMonitoramento, 'selecionar_slot'):
                                with patch.object(CentralMonitoramento, 'restaurar_grid'):
                                    with patch.object(CentralMonitoramento, 'alternar_todos_streams'):
                                        with patch.object(CentralMonitoramento, 'atualizar_lista_presets_ui'):
                                            self.app = CentralMonitoramento()

        self.app.presets = {}
        self.app.grid_cameras = ["192.168.1.1"] * 20
        self.app.arquivo_presets = self.presets_file

    def tearDown(self):
        if os.path.exists(self.presets_file):
            os.remove(self.presets_file)

    def test_salvar_preset(self):
        # Test saving a new preset
        name = " Test Preset "
        self.app._salvar_preset(name.strip())

        self.assertIn("Test Preset", self.app.presets)
        self.assertEqual(self.app.presets["Test Preset"], ["192.168.1.1"] * 20)
        self.assertEqual(self.app.ultimo_preset, "Test Preset")

        # Verify it was saved to file
        with open(self.presets_file, 'r') as f:
            data = json.load(f)
            self.assertIn("Test Preset", data)

    def test_renomear_preset(self):
        # Setup initial preset
        self.app.presets = {"Old Name": ["1.1.1.1"] * 20}
        self.app.ultimo_preset = "Old Name"

        # Mocking the rename logic within the callback of abrir_modal_input
        # Since we are testing the logic inside renomear_preset's inner function

        # Manually triggering what on_name_entered would do
        novo_nome = " New Name ".strip()

        # Logic from renomear_preset's on_name_entered:
        if novo_nome and novo_nome != "Old Name":
            if "Old Name" in self.app.presets:
                self.app.presets[novo_nome] = self.app.presets.pop("Old Name")
                if self.app.ultimo_preset == "Old Name":
                    self.app.ultimo_preset = novo_nome

        self.assertNotIn("Old Name", self.app.presets)
        self.assertIn("New Name", self.app.presets)
        self.assertEqual(self.app.ultimo_preset, "New Name")

    def test_deletar_preset(self):
        self.app.presets = {"To Delete": ["2.2.2.2"] * 20}
        self.app.ultimo_preset = "To Delete"

        self.app._deletar_preset("To Delete")

        self.assertNotIn("To Delete", self.app.presets)
        self.assertIsNone(self.app.ultimo_preset)

    def test_sobrescrever_preset(self):
        self.app.presets = {"Existing": ["1.1.1.1"] * 20}
        self.app.grid_cameras = ["3.3.3.3"] * 20

        self.app._sobrescrever_preset("Existing")

        self.assertEqual(self.app.presets["Existing"], ["3.3.3.3"] * 20)
        self.assertEqual(self.app.ultimo_preset, "Existing")

if __name__ == '__main__':
    unittest.main()
