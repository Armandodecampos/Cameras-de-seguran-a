import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Define a Fake widget that has common methods
class FakeWidget:
    def __init__(self, *args, **kwargs):
        self._pack_info = {}
        self._grid_info = {}
    def pack(self, **kwargs): self._pack_info = kwargs
    def grid(self, **kwargs): self._grid_info = kwargs
    def pack_forget(self): pass
    def grid_forget(self): pass
    def configure(self, **kwargs): pass
    def cget(self, attr): return ""
    def winfo_width(self): return 100
    def winfo_height(self): return 100
    def winfo_ismapped(self): return True
    def lift(self): pass
    def destroy(self): pass
    def bind(self, *args, **kwargs): pass
    def place(self, **kwargs): pass
    def place_forget(self): pass
    def winfo_children(self): return []
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def pack_propagate(self, *args): pass
    def after(self, *args, **kwargs): pass
    def add(self, name): return FakeWidget()
    def tab(self, name): return FakeWidget()
    def get(self): return "Câmeras"
    def set(self, name): pass
    def insert(self, idx, val): pass
    def delete(self, start, end): pass
    def pack_configure(self, **kwargs): pass
    def grid_configure(self, **kwargs): pass
    def update_idletasks(self): pass

# Create a more robust mock for customtkinter
class FakeCTk(FakeWidget):
    def title(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): pass
    def protocol(self, *args, **kwargs): pass
    def mainloop(self, *args, **kwargs): pass
    def withdraw(self): pass
    def deiconify(self): pass
    def _get_window_scaling(self): return 1.0

mock_ctk = MagicMock()
mock_ctk.CTk = FakeCTk
mock_ctk.CTkFrame = FakeWidget
mock_ctk.CTkTabview = FakeWidget
mock_ctk.CTkScrollableFrame = FakeWidget
mock_ctk.CTkLabel = FakeWidget
mock_ctk.CTkEntry = FakeWidget
mock_ctk.CTkButton = FakeWidget
mock_ctk.CTkImage = MagicMock()
mock_ctk.set_appearance_mode = MagicMock
sys.modules["customtkinter"] = mock_ctk

# Mock other heavy dependencies
sys.modules["cv2"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.ImageTk"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["requests.auth"] = MagicMock()

import Cameras
from Cameras import CentralMonitoramento

class TestPredefinicoes(unittest.TestCase):
    def setUp(self):
        # Patch methods that would interact with the OS or UI in __init__
        with patch.object(CentralMonitoramento, 'carregar_posicao_janela'), \
             patch.object(CentralMonitoramento, 'carregar_predefinicoes', return_value={}), \
             patch.object(CentralMonitoramento, 'carregar_lista_ips', return_value=[]), \
             patch.object(CentralMonitoramento, 'carregar_config', return_value={}), \
             patch.object(CentralMonitoramento, 'carregar_grid', return_value=["0.0.0.0"]*20), \
             patch.object(CentralMonitoramento, 'atualizar_lista_cameras_ui'), \
             patch.object(CentralMonitoramento, 'atualizar_lista_predefinicoes_ui'), \
             patch.object(CentralMonitoramento, 'selecionar_slot'), \
             patch.object(CentralMonitoramento, 'alternar_todos_streams'), \
             patch.object(CentralMonitoramento, 'loop_exibicao'):

            self.app = CentralMonitoramento()
            self.app.predefinicoes = {}
            self.app.grid_cameras = ["192.168.1.1"] + ["0.0.0.0"]*19

    def test_salvar_predefinicao(self):
        nome = "Teste"
        with patch.object(self.app, 'salvar_predefinicoes'), \
             patch.object(self.app, 'atualizar_lista_predefinicoes_ui'):
            self.app._salvar_predefinicao(nome)

        self.assertIn(nome, self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes[nome], self.app.grid_cameras)
        self.assertEqual(self.app.ultima_predefinicao, nome)

    def test_aplicar_predefinicao(self):
        nome = "Teste"
        grid_salvo = ["192.168.1.100"] * 20
        self.app.predefinicoes[nome] = grid_salvo

        with patch.object(self.app, 'atribuir_ip_ao_slot') as mock_atribuir, \
             patch.object(self.app, 'iniciar_conexao_assincrona') as mock_conexao, \
             patch.object(self.app, 'selecionar_slot'), \
             patch.object(self.app, 'update_idletasks'), \
             patch.object(self.app, 'pintar_predefinicao'), \
             patch.object(self.app, 'salvar_grid'):

            self.app.aplicar_predefinicao(nome)

            self.assertEqual(self.app.ultima_predefinicao, nome)
            # Should be called 20 times to update the grid
            self.assertEqual(mock_atribuir.call_count, 20)
            # Should be called once for the unique IP in the preset
            self.assertEqual(mock_conexao.call_count, 1)
            mock_conexao.assert_called_with("192.168.1.100", 102)

    def test_deletar_predefinicao(self):
        nome = "Teste"
        self.app.predefinicoes[nome] = ["0.0.0.0"]*20
        self.app.ultima_predefinicao = nome

        with patch.object(self.app, 'salvar_predefinicoes'), \
             patch.object(self.app, 'atualizar_lista_predefinicoes_ui'), \
             patch.object(self.app, 'abrir_modal_confirmacao') as mock_confirm:

            # Simulate confirm action
            self.app.deletar_predefinicao(nome)
            callback_sim = mock_confirm.call_args[0][2]
            callback_sim()

            self.assertNotIn(nome, self.app.predefinicoes)
            self.assertIsNone(self.app.ultima_predefinicao)

    def test_renomear_predefinicao(self):
        nome_antigo = "Antigo"
        nome_novo = "Novo"
        grid = ["192.168.1.1"] * 20
        self.app.predefinicoes[nome_antigo] = grid
        self.app.ultima_predefinicao = nome_antigo

        with patch.object(self.app, 'abrir_modal_input') as mock_input, \
             patch.object(self.app, 'salvar_predefinicoes'), \
             patch.object(self.app, 'atualizar_lista_predefinicoes_ui'):

            self.app.renomear_predefinicao(nome_antigo)

            callback = mock_input.call_args[0][2]
            callback(nome_novo)

            self.assertNotIn(nome_antigo, self.app.predefinicoes)
            self.assertIn(nome_novo, self.app.predefinicoes)
            self.assertEqual(self.app.predefinicoes[nome_novo], grid)
            self.assertEqual(self.app.ultima_predefinicao, nome_novo)

if __name__ == "__main__":
    unittest.main()
