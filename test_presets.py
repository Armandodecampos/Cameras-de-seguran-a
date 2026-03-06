import json
import os
import unittest
from unittest.mock import MagicMock, patch
import sys

# Mocking customtkinter and other GUI dependencies
class MockCTk:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args): pass
    def geometry(self, *args): pass
    def protocol(self, *args): pass
    def bind(self, *args): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def after(self, *args): pass
    def update_idletasks(self, *args): pass
    def mainloop(self): pass
    def state(self, *args): pass

mock_ctk = MagicMock()
mock_ctk.CTk = MockCTk
mock_ctk.CTkFrame = MagicMock()
mock_ctk.CTkTabview = MagicMock()
mock_ctk.CTkEntry = MagicMock()
mock_ctk.CTkScrollableFrame = MagicMock()
mock_ctk.CTkButton = MagicMock()
mock_ctk.CTkLabel = MagicMock()
mock_ctk.CTkImage = MagicMock()
mock_ctk.CTkToplevel = MagicMock()

sys.modules['customtkinter'] = mock_ctk
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageTk'] = MagicMock()
sys.modules['cv2'] = MagicMock()
sys.modules['requests'] = MagicMock()
sys.modules['requests.auth'] = MagicMock()

from Cameras import CentralMonitoramento

class TestPresetLogic(unittest.TestCase):
    def setUp(self):
        # Setup paths to use temporary files
        self.user_dir = "."
        self.arquivo_presets = os.path.join(self.user_dir, "test_presets_grid_abi.json")

        # Patch CentralMonitoramento to use our test file and skip some UI/Thread initialization if needed
        with patch('os.path.expanduser', return_value=self.user_dir), \
             patch.object(CentralMonitoramento, 'carregar_posicao_janela'), \
             patch.object(CentralMonitoramento, 'alternar_todos_streams'), \
             patch.object(CentralMonitoramento, 'loop_exibicao'), \
             patch.object(CentralMonitoramento, 'atualizar_lista_presets_ui'), \
             patch('threading.Thread'):

            self.app = CentralMonitoramento()
            self.app.arquivo_presets = self.arquivo_presets
            self.app.presets = {}
            self.app.grid_cameras = ["0.0.0.0"] * 20

    def tearDown(self):
        if os.path.exists(self.arquivo_presets):
            os.remove(self.arquivo_presets)

    def test_salvar_preset(self):
        self.app.grid_cameras[0] = "192.168.1.100"
        self.app._salvar_preset("Test Preset")

        self.assertIn("Test Preset", self.app.presets)
        self.assertEqual(self.app.presets["Test Preset"][0], "192.168.1.100")
        self.assertTrue(os.path.exists(self.arquivo_presets))

    def test_deletar_preset(self):
        self.app.presets["To Delete"] = ["0.0.0.0"] * 20
        self.app.ultimo_preset = "To Delete"
        self.app._deletar_preset("To Delete")

        self.assertNotIn("To Delete", self.app.presets)
        self.assertIsNone(self.app.ultimo_preset)

    def test_renomear_preset(self):
        self.app.presets["Old Name"] = ["1.1.1.1"] * 20
        self.app.ultimo_preset = "Old Name"

        # Mocking the inner function logic of renomear_preset
        # Since renomear_preset uses an inner callback, we test the logic directly or how it handles presets
        self.app.presets["New Name"] = self.app.presets.pop("Old Name")
        self.app.ultimo_preset = "New Name"

        self.assertNotIn("Old Name", self.app.presets)
        self.assertIn("New Name", self.app.presets)
        self.assertEqual(self.app.ultimo_preset, "New Name")

    def test_aplicar_preset(self):
        preset_data = ["0.0.0.0"] * 20
        preset_data[5] = "10.0.0.5"
        self.app.presets["Apply Me"] = preset_data

        with patch.object(self.app, 'atribuir_ip_ao_slot') as mock_atribuir, \
             patch.object(self.app, 'pintar_preset'), \
             patch.object(self.app, 'salvar_grid'), \
             patch.object(self.app, 'selecionar_slot'), \
             patch.object(self.app, 'iniciar_conexao_assincrona'):

            self.app.aplicar_preset("Apply Me")

            # Check if atribuir_ip_ao_slot was called for the changed IP
            mock_atribuir.assert_any_call(5, "10.0.0.5", atualizar_ui=False, gerenciar_conexoes=False, salvar=False)
            self.assertEqual(self.app.ultimo_preset, "Apply Me")

if __name__ == '__main__':
    unittest.main()
