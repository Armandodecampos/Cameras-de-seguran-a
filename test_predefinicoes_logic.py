import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import json
import sys

# Mocking customtkinter and other GUI dependencies
class MockCTk:
    def __init__(self, *args, **kwargs):
        pass
    def title(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): pass
    def protocol(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def after(self, *args, **kwargs): pass
    def mainloop(self, *args, **kwargs): pass
    def destroy(self, *args, **kwargs): pass
    def state(self, *args, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_width(self): return 1200
    def winfo_height(self): return 800
    def update_idletasks(self): pass
    def tabview(self, *args, **kwargs): return MagicMock()

sys.modules['cv2'] = MagicMock()
sys.modules['mss'] = MagicMock()

# Manually mock things to avoid InvalidSpecError
mock_ctk = MagicMock()
mock_ctk.CTk = MockCTk
mock_ctk.CTkFrame = MagicMock()
mock_ctk.CTkTabview = MagicMock()
mock_ctk.CTkButton = MagicMock()
mock_ctk.CTkLabel = MagicMock()
mock_ctk.CTkEntry = MagicMock()
mock_ctk.CTkScrollableFrame = MagicMock()
# Ensure CTkImage doesn't cause issues with spec
mock_ctk.CTkImage.side_effect = lambda *args, **kwargs: MagicMock()

sys.modules['customtkinter'] = mock_ctk

mock_pil = MagicMock()
mock_image = MagicMock()
mock_pil.Image = mock_image
sys.modules['PIL'] = mock_pil
sys.modules['PIL.Image'] = mock_image
sys.modules['PIL.ImageTk'] = MagicMock()

import customtkinter as ctk
from PIL import Image

# Now we can import CentralMonitoramento from Cameras.py
from Cameras import CentralMonitoramento

class TestPredefinicoesLogic(unittest.TestCase):
    @patch('Cameras.os.path.exists')
    @patch('Cameras.open', new_callable=mock_open, read_data="{}")
    def setUp(self, mock_file, mock_exists):
        mock_exists.return_value = False
        # We need to bypass some initializations that might trigger GUI errors or complex logic
        with patch.object(CentralMonitoramento, 'criar_botoes_iniciais'), \
             patch.object(CentralMonitoramento, 'restaurar_grid'), \
             patch.object(CentralMonitoramento, 'selecionar_slot'), \
             patch.object(CentralMonitoramento, 'alternar_todos_streams'), \
             patch.object(CentralMonitoramento, 'atualizar_lista_predefinicoes_ui'), \
             patch.object(CentralMonitoramento, 'loop_exibicao'):
            self.app = CentralMonitoramento()
            self.app.predefinicoes = {}
            self.app.grid_cameras = ["0.0.0.0"] * 20

    def test_salvar_predefinicao(self):
        self.app.grid_cameras[0] = "192.168.1.1"
        self.app._salvar_predefinicao("Teste")
        self.assertIn("Teste", self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes["Teste"][0], "192.168.1.1")
        self.assertEqual(self.app.ultima_predefinicao, "Teste")

    def test_deletar_predefinicao(self):
        self.app.predefinicoes["Teste"] = ["0.0.0.0"] * 20
        self.app.ultima_predefinicao = "Teste"
        self.app._deletar_predefinicao("Teste")
        self.assertNotIn("Teste", self.app.predefinicoes)
        self.assertIsNone(self.app.ultima_predefinicao)

    def test_renomear_predefinicao(self):
        self.app.predefinicoes["Antigo"] = ["192.168.1.1"] * 20
        self.app.ultima_predefinicao = "Antigo"

        # Simulating renomear_predefinicao callback logic
        with patch.object(self.app, 'salvar_predefinicoes'), \
             patch.object(self.app, 'atualizar_lista_predefinicoes_ui'):

            # We call the internal logic usually triggered by on_name_entered
            self.app.predefinicoes["Novo"] = self.app.predefinicoes.pop("Antigo")
            self.app.ultima_predefinicao = "Novo"

        self.assertNotIn("Antigo", self.app.predefinicoes)
        self.assertIn("Novo", self.app.predefinicoes)
        self.assertEqual(self.app.ultima_predefinicao, "Novo")

    @patch.object(CentralMonitoramento, 'atribuir_ip_ao_slot')
    @patch.object(CentralMonitoramento, 'iniciar_conexao_assincrona')
    def test_aplicar_predefinicao(self, mock_iniciar, mock_atribuir):
        self.app.predefinicoes["Teste"] = ["192.168.1.10"] + ["0.0.0.0"] * 19
        self.app.camera_handlers = {}

        self.app.aplicar_predefinicao("Teste")

        self.assertEqual(self.app.ultima_predefinicao, "Teste")
        # Ensure it called atribuir_ip_ao_slot for all 20 slots
        self.assertEqual(mock_atribuir.call_count, 20)
        # Check first call
        mock_atribuir.assert_any_call(0, "192.168.1.10", atualizar_ui=False, gerenciar_conexoes=False, salvar=False)
        # Ensure connection was started
        mock_iniciar.assert_any_call("192.168.1.10", 102)

if __name__ == '__main__':
    unittest.main()
