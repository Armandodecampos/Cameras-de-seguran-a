import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys
import queue

# Mocking modules that might not be available or are GUI-heavy
mock_ctk = MagicMock()
class FakeCTk:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): pass
    def protocol(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def after(self, *args, **kwargs): pass

mock_ctk.CTk = FakeCTk
sys.modules['customtkinter'] = mock_ctk
sys.modules['cv2'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageTk'] = MagicMock()

import Cameras

class TestPredefinicoesLogic(unittest.TestCase):
    def setUp(self):
        # Avoid calling __init__ which starts GUI and threads
        self.app = Cameras.CentralMonitoramento.__new__(Cameras.CentralMonitoramento)
        self.app.predefinicoes = {}
        self.app.grid_cameras = ["0.0.0.0"] * 20
        self.app.ultima_predefinicao = None
        self.app.arquivo_predefinicoes = "test_predefinicoes.json"

        # Mock methods that interact with UI or files
        self.app.salvar_predefinicoes = MagicMock()
        self.app.atualizar_lista_predefinicoes_ui = MagicMock()
        self.app.abrir_modal_input = MagicMock()
        self.app.abrir_modal_confirmacao = MagicMock()
        self.app.abrir_modal_alerta = MagicMock()
        self.app.pintar_predefinicao = MagicMock()
        self.app.atribuir_ip_ao_slot = MagicMock()
        self.app.salvar_grid = MagicMock()
        self.app.iniciar_conexao_assincrona = MagicMock()
        self.app.restaurar_grid = MagicMock()
        self.app.selecionar_slot = MagicMock()
        self.app.update_idletasks = MagicMock()
        self.app.slot_maximized = None
        self.app.slot_selecionado = 0
        self.app.camera_handlers = {}
        self.app.fila_pendente_conexoes = queue.Queue()
        self.app.ips_em_fila = set()
        self.app.cooldown_conexoes = {}
        self.app.BG_SIDEBAR = "#1A1A1A"
        self.app.ACCENT_WINE = "#7B1010"

    def test_salvar_predefinicao(self):
        self.app.grid_cameras[0] = "192.168.1.1"
        self.app._salvar_predefinicao("Teste")

        self.assertEqual(self.app.predefinicoes["Teste"][0], "192.168.1.1")
        self.assertEqual(self.app.ultima_predefinicao, "Teste")
        self.app.salvar_predefinicoes.assert_called_once()
        self.app.atualizar_lista_predefinicoes_ui.assert_called_once()

    def test_aplicar_predefinicao(self):
        self.app.predefinicoes["Teste"] = ["192.168.1.2"] + ["0.0.0.0"] * 19
        self.app.fila_pendente_conexoes.put(("old_ip", 102))
        self.app.ips_em_fila = {"old_ip"}

        self.app.aplicar_predefinicao("Teste")

        self.assertEqual(self.app.ultima_predefinicao, "Teste")
        self.assertEqual(self.app.cooldown_conexoes, {}) # Verified it was cleared
        self.assertEqual(self.app.ips_em_fila, set())
        self.assertTrue(self.app.fila_pendente_conexoes.empty())
        self.app.atribuir_ip_ao_slot.assert_called()
        self.app.iniciar_conexao_assincrona.assert_called_with("192.168.1.2", 102)

    def test_deletar_predefinicao(self):
        self.app.predefinicoes["Teste"] = ["0.0.0.0"] * 20
        self.app.ultima_predefinicao = "Teste"

        self.app._deletar_predefinicao("Teste")

        self.assertNotIn("Teste", self.app.predefinicoes)
        self.assertIsNone(self.app.ultima_predefinicao)
        self.app.salvar_predefinicoes.assert_called_once()

    def test_renomear_predefinicao(self):
        self.app.predefinicoes["Antigo"] = ["1.1.1.1"] * 20
        self.app.ultima_predefinicao = "Antigo"

        # Simulate on_name_entered callback
        def mock_modal_input(title, msg, callback, valor_inicial=""):
            callback("Novo")

        self.app.abrir_modal_input.side_effect = mock_modal_input

        self.app.renomear_predefinicao("Antigo")

        self.assertNotIn("Antigo", self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes["Novo"][0], "1.1.1.1")
        self.assertEqual(self.app.ultima_predefinicao, "Novo")

if __name__ == "__main__":
    unittest.main()
