import unittest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock
from Cameras import CentralMonitoramento

class TestPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patcher = patch('os.path.expanduser', return_value=self.temp_dir)
        self.patcher.start()
        self.app = CentralMonitoramento()

    def tearDown(self):
        try:
            self.app.destroy()
        except:
            pass
        self.patcher.stop()

    def test_salvar_varias_predefinicoes(self):
        """Testa o salvamento de múltiplas predefinições e sua persistência."""
        # Configura grid 1
        grid1 = [f"192.168.7.{i+10}" for i in range(16)]
        self.app.grid_cameras = list(grid1)
        self.app._executar_salvamento_preset("Setor Portaria")

        # Configura grid 2
        grid2 = [f"192.168.7.{i+50}" for i in range(16)]
        self.app.grid_cameras = list(grid2)
        self.app._executar_salvamento_preset("Setor Galpão")

        # Verifica se ambas as predefinições foram salvas em memória
        self.assertIn("Setor Portaria", self.app.presets_salvos)
        self.assertIn("Setor Galpão", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Setor Portaria"], grid1)
        self.assertEqual(self.app.presets_salvos["Setor Galpão"], grid2)

        # Verifica se foram persistidas no arquivo JSON
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados_salvos = json.load(f)
        self.assertIn("Setor Portaria", dados_salvos)
        self.assertIn("Setor Galpão", dados_salvos)

    def test_aplicar_predefinicao(self):
        """Testa o carregamento/aplicação de uma predefinição completa no grid."""
        grid_esperado = [f"192.168.7.{i+20}" for i in range(16)]
        self.app.grid_cameras = list(grid_esperado)
        self.app._executar_salvamento_preset("Setor Especial")

        # Zera o grid atual
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # Aplica a predefinição
        self.app.aplicar_preset("Setor Especial")

        # Verifica se todos os 16 slots foram preenchidos corretamente
        self.assertEqual(self.app.grid_cameras, grid_esperado)

        # Verifica se o arquivo do grid principal também foi atualizado
        with open(self.app.arquivo_grid, "r", encoding="utf-8") as f:
            grid_arquivo = json.load(f)
        self.assertEqual(grid_arquivo, grid_esperado)

    def test_renomear_predefinicao(self):
        """Testa renomear uma predefinição existente."""
        grid_original = ["192.168.7.2", "192.168.7.3"] + ["0.0.0.0"] * 14
        self.app.grid_cameras = list(grid_original)
        self.app._executar_salvamento_preset("Antigo Nome")

        self.assertIn("Antigo Nome", self.app.presets_salvos)

        # Executa a renomeação
        self.app._executar_renomear_preset("Antigo Nome", "Novo Nome")

        self.assertNotIn("Antigo Nome", self.app.presets_salvos)
        self.assertIn("Novo Nome", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo Nome"], grid_original)

        # Verifica persistência no JSON
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados_salvos = json.load(f)
        self.assertNotIn("Antigo Nome", dados_salvos)
        self.assertIn("Novo Nome", dados_salvos)

    def test_deletar_predefinicao(self):
        """Testa deletar uma predefinição."""
        self.app.grid_cameras = ["192.168.7.2"] + ["0.0.0.0"] * 15
        self.app._executar_salvamento_preset("Predefinição Para Deletar")

        self.assertIn("Predefinição Para Deletar", self.app.presets_salvos)

        # Executa a exclusão
        self.app.excluir_preset("Predefinição Para Deletar")

        self.assertNotIn("Predefinição Para Deletar", self.app.presets_salvos)

        # Verifica persistência no JSON
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados_salvos = json.load(f)
        self.assertNotIn("Predefinição Para Deletar", dados_salvos)

    def test_ui_predefinicoes_clicavel_e_botoes(self):
        """Testa criação dos elementos da UI de predefinições e interação."""
        self.app.mudar_aba_sidebar("Predefinições")
        self.app.grid_cameras = ["192.168.7.100"] + ["0.0.0.0"] * 15
        self.app._executar_salvamento_preset("Setor Teste UI")

        self.assertEqual(len(self.app.preset_labels_referencia), 1)
        self.assertEqual(self.app.preset_labels_referencia[0].cget("text"), "Setor Teste UI")

        # Modifica o grid
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # Simula clique para carregar a predefinição
        self.app.aplicar_preset("Setor Teste UI")
        self.assertEqual(self.app.grid_cameras[0], "192.168.7.100")


if __name__ == "__main__":
    unittest.main()
