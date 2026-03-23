import sys
import os
import json
import unittest
from unittest.mock import MagicMock

# Mock customtkinter and other dependencies before importing CentralMonitoramento
class CTkMock:
    def __init__(self, *args, **kwargs): pass
    def grid(self, *args, **kwargs): pass
    def pack(self, *args, **kwargs): pass
    def configure(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def unbind(self, *args, **kwargs): pass
    def winfo_children(self): return []

sys.modules['customtkinter'] = MagicMock()
import customtkinter as ctk
ctk.CTk = CTkMock
ctk.CTkFrame = CTkMock
ctk.CTkLabel = CTkMock
ctk.CTkButton = CTkMock
ctk.CTkScrollableFrame = CTkMock
ctk.CTkEntry = CTkMock
ctk.CTkTabview = MagicMock()
ctk.CTkImage = MagicMock()
ctk.set_appearance_mode = MagicMock()

# Mock PIL
sys.modules['PIL'] = MagicMock()
from PIL import Image

# Mock cv2
sys.modules['cv2'] = MagicMock()
import cv2

# Now we can import CentralMonitoramento
from Cameras import CentralMonitoramento

class TestPredefinicoesLogic(unittest.TestCase):
    def setUp(self):
        # Create a mock for the app that bypasses most of the __init__ logic or handles it safely
        CentralMonitoramento._get_window_scaling = lambda x: 1.0

        # We need to mock several methods to avoid GUI issues during init
        self.app = CentralMonitoramento.__new__(CentralMonitoramento)

        # Initialize necessary attributes manually
        self.app.BG_SIDEBAR = "#1A1A1A"
        self.app.ACCENT_WINE = "#7B1010"
        self.app.arquivo_predefinicoes = "test_predefinicoes.json"
        self.app.arquivo_grid = "test_grid.json"
        self.app.grid_cameras = ["0.0.0.0"] * 20
        self.app.predefinicoes = {}
        self.app.ultima_predefinicao = None
        self.app.predefinicao_widgets = {}
        self.app.camera_handlers = {}
        self.app.cooldown_conexoes = {}
        self.app.slot_maximized = None
        self.app.slot_selecionado = 0

        # Mock UI update methods
        self.app.atualizar_lista_predefinicoes_ui = MagicMock()
        self.app.pintar_predefinicao = MagicMock()
        self.app.atribuir_ip_ao_slot = MagicMock()
        self.app.salvar_grid = MagicMock()
        self.app.iniciar_conexao_assincrona = MagicMock()
        self.app.restaurar_grid = MagicMock()
        self.app.selecionar_slot = MagicMock()
        self.app.update_idletasks = MagicMock()
        self.app.abrir_modal_confirmacao = MagicMock()
        self.app.abrir_modal_input = MagicMock()
        self.app.abrir_modal_alerta = MagicMock()

    def tearDown(self):
        if os.path.exists("test_predefinicoes.json"):
            os.remove("test_predefinicoes.json")
        if os.path.exists("test_grid.json"):
            os.remove("test_grid.json")

    def test_salvar_predefinicao(self):
        self.app.grid_cameras[0] = "1.2.3.4"
        self.app._salvar_predefinicao("Teste")

        self.assertEqual(self.app.predefinicoes["Teste"], self.app.grid_cameras)
        self.assertEqual(self.app.ultima_predefinicao, "Teste")
        self.app.atualizar_lista_predefinicoes_ui.assert_called_once()

        with open("test_predefinicoes.json", "r") as f:
            data = json.load(f)
            self.assertEqual(data["Teste"], self.app.grid_cameras)

    def test_excluir_predefinicao(self):
        self.app.predefinicoes["ParaDeletar"] = ["0.0.0.0"] * 20
        self.app.ultima_predefinicao = "ParaDeletar"

        self.app._excluir_predefinicao("ParaDeletar")

        self.assertNotIn("ParaDeletar", self.app.predefinicoes)
        self.assertIsNone(self.app.ultima_predefinicao)
        self.app.atualizar_lista_predefinicoes_ui.assert_called_once()

    def test_renomear_predefinicao(self):
        grid = ["0.0.0.0"] * 20
        grid[5] = "5.5.5.5"
        self.app.predefinicoes["Antigo"] = grid
        self.app.ultima_predefinicao = "Antigo"

        # We need to simulate the callback of abrir_modal_input for renomear_predefinicao
        def mock_input(titulo, msg, callback, valor_inicial=""):
            callback("Novo")

        self.app.abrir_modal_input = mock_input
        self.app.renomear_predefinicao("Antigo")

        self.assertNotIn("Antigo", self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes["Novo"], grid)
        self.assertEqual(self.app.ultima_predefinicao, "Novo")
        self.app.atualizar_lista_predefinicoes_ui.assert_called_once()

    def test_aplicar_predefinicao(self):
        grid_alvo = ["0.0.0.0"] * 20
        grid_alvo[0] = "10.0.0.1"
        grid_alvo[1] = "10.0.0.2"
        self.app.predefinicoes["Layout1"] = grid_alvo

        self.app.aplicar_predefinicao("Layout1")

        self.assertEqual(self.app.ultima_predefinicao, "Layout1")
        # Deve chamar atribuir_ip_ao_slot para cada um dos 20 slots
        self.assertEqual(self.app.atribuir_ip_ao_slot.call_count, 20)

        # Verifica se chamou com os parâmetros otimizados
        self.app.atribuir_ip_ao_slot.assert_any_call(0, "10.0.0.1", atualizar_ui=False, gerenciar_conexoes=False, salvar=False, forcado=True)

        self.app.salvar_grid.assert_called_once()
        self.app.iniciar_conexao_assincrona.assert_any_call("10.0.0.1", 102)
        self.app.iniciar_conexao_assincrona.assert_any_call("10.0.0.2", 102)

if __name__ == '__main__':
    unittest.main()
