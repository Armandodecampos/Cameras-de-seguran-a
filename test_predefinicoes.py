import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import json
import sys

# Mock de dependências de GUI e hardware antes de importar CentralMonitoramento
class FakeCTkImage:
    def __init__(self, *args, **kwargs): pass
    def configure(self, *args, **kwargs): pass

class FakeCTk:
    def __init__(self, *args, **kwargs): pass
    def title(self, *args, **kwargs): pass
    def geometry(self, *args, **kwargs): pass
    def protocol(self, *args, **kwargs): pass
    def bind(self, *args, **kwargs): pass
    def after(self, *args, **kwargs): pass
    def state(self, *args, **kwargs): pass
    def mainloop(self, *args, **kwargs): pass
    def update_idletasks(self, *args, **kwargs): pass
    def destroy(self, *args, **kwargs): pass
    def grid_columnconfigure(self, *args, **kwargs): pass
    def grid_rowconfigure(self, *args, **kwargs): pass
    def winfo_x(self): return 0
    def winfo_y(self): return 0
    def winfo_width(self): return 1200
    def winfo_height(self): return 800
    def _get_window_scaling(self): return 1.0

mock_ctk = MagicMock()
mock_ctk.CTk = FakeCTk
mock_ctk.CTkFrame = MagicMock()
mock_ctk.CTkLabel = MagicMock()
mock_ctk.CTkButton = MagicMock()
mock_ctk.CTkEntry = MagicMock()
mock_ctk.CTkScrollableFrame = MagicMock()
mock_ctk.CTkTabview = MagicMock()
mock_ctk.CTkToplevel = MagicMock()
mock_ctk.CTkImage = FakeCTkImage
mock_ctk.set_appearance_mode = MagicMock()

sys.modules['customtkinter'] = mock_ctk
sys.modules['cv2'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['PIL.ImageTk'] = MagicMock()

from Cameras import CentralMonitoramento

class TestPredefinicoes(unittest.TestCase):
    def setUp(self):
        # Patch de arquivos para não ler/escrever no disco real
        self.patcher_open = patch('builtins.open', mock_open(read_data='{}'))
        self.mock_file = self.patcher_open.start()

        with patch('os.path.exists', return_value=False):
            self.app = CentralMonitoramento()

        # Estado inicial limpo
        self.app.predefinicoes = {}
        self.app.grid_cameras = ["0.0.0.0"] * 20
        self.app.ultima_predefinicao = None

    def tearDown(self):
        self.patcher_open.stop()

    def test_salvar_nova_predefinicao(self):
        """Testa se uma nova predefinição é salva corretamente."""
        nome = "Teste Preset"
        self.app.grid_cameras[0] = "192.168.1.10"

        # Simula o callback do modal de input
        self.app._salvar_predefinicao(nome)

        self.assertIn(nome, self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes[nome][0], "192.168.1.10")
        self.assertEqual(self.app.ultima_predefinicao, nome)

    def test_aplicar_predefinicao(self):
        """Testa se a aplicação de uma predefinição limpa a fila e atualiza o grid."""
        nome = "Teste Preset"
        self.app.predefinicoes[nome] = ["192.168.1.50"] + ["0.0.0.0"] * 19

        # Adiciona algo na fila de conexões para testar a limpeza
        self.app.fila_pendente_conexoes.put(("1.1.1.1", 102))
        self.app.ips_em_fila.add("1.1.1.1")

        with patch.object(self.app, 'iniciar_conexao_assincrona') as mock_conn:
            self.app.aplicar_predefinicao(nome)

            # Verifica se a fila foi limpa
            self.assertTrue(self.app.fila_pendente_conexoes.empty())
            self.assertEqual(len(self.app.ips_em_fila), 0)

            # Verifica se o grid foi atualizado
            self.assertEqual(self.app.grid_cameras[0], "192.168.1.50")

            # Verifica se as conexões foram iniciadas
            mock_conn.assert_called_with("192.168.1.50", 102)

    def test_renomear_predefinicao(self):
        """Testa o renomeio de uma predefinição existente chamando o método real."""
        nome_antigo = "Antigo"
        nome_novo = "Novo"
        self.app.predefinicoes[nome_antigo] = ["192.168.1.1"] * 20
        self.app.ultima_predefinicao = nome_antigo

        # Patch abrir_modal_input para executar o callback imediatamente com o novo nome
        with patch.object(self.app, 'abrir_modal_input') as mock_input:
            mock_input.side_effect = lambda tit, msg, cb, valor_inicial="": cb(nome_novo)
            self.app.renomear_predefinicao(nome_antigo)

        self.assertNotIn(nome_antigo, self.app.predefinicoes)
        self.assertIn(nome_novo, self.app.predefinicoes)
        self.assertEqual(self.app.ultima_predefinicao, nome_novo)

    def test_salvar_predefinicao_atual_via_interface(self):
        """Testa salvar a predefinição atual via interface modal."""
        nome = "Novo Preset via UI"
        self.app.grid_cameras[0] = "10.0.0.1"

        with patch.object(self.app, 'abrir_modal_input') as mock_input:
            mock_input.side_effect = lambda tit, msg, cb, valor_inicial="": cb(nome)
            self.app.salvar_predefinicao_atual()

        self.assertIn(nome, self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes[nome][0], "10.0.0.1")

    def test_deletar_predefinicao(self):
        """Testa a exclusão de uma predefinição."""
        nome = "Deletar"
        self.app.predefinicoes[nome] = ["0.0.0.0"] * 20
        self.app.ultima_predefinicao = nome

        self.app._deletar_predefinicao(nome)

        self.assertNotIn(nome, self.app.predefinicoes)
        self.assertIsNone(self.app.ultima_predefinicao)

if __name__ == "__main__":
    unittest.main()
