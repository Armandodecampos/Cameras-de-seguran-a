import unittest
import os
import json
import shutil
import tempfile
import customtkinter as ctk

# Import CentralMonitoramento from Cameras
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.arquivo_presets = os.path.join(self.temp_dir, "test_presets.json")
        self.arquivo_grid = os.path.join(self.temp_dir, "test_grid.json")
        self.arquivo_janela = os.path.join(self.temp_dir, "test_janela.json")
        self.arquivo_ips = os.path.join(self.temp_dir, "test_ips.json")
        self.arquivo_config = os.path.join(self.temp_dir, "test_config.json")

        # Mock app creation
        self.app = CentralMonitoramento()
        self.app.withdraw() # Hide window during test

        # Override file paths
        self.app.arquivo_presets = self.arquivo_presets
        self.app.arquivo_grid = self.arquivo_grid
        self.app.arquivo_janela = self.arquivo_janela
        self.app.arquivo_ips = self.arquivo_ips
        self.app.arquivo_config = self.arquivo_config

        # Initialize clean state
        self.app.presets_salvos = {}
        self.app.grid_cameras = ["0.0.0.0"] * self.app.MAX_SLOTS

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_salvar_varias_predefinicoes(self):
        """Test saving multiple camera presets and checking file persistence."""
        grid1 = ["192.168.7.2", "192.168.7.3"] + ["0.0.0.0"] * 14
        self.app.grid_cameras = list(grid1)
        self.app._executar_salvamento_preset("Preset 1")

        grid2 = ["192.168.7.10", "192.168.7.20", "192.168.7.30"] + ["0.0.0.0"] * 13
        self.app.grid_cameras = list(grid2)
        self.app._executar_salvamento_preset("Preset 2")

        self.assertIn("Preset 1", self.app.presets_salvos)
        self.assertIn("Preset 2", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset 1"], grid1)
        self.assertEqual(self.app.presets_salvos["Preset 2"], grid2)

        # Check JSON file content
        with open(self.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertIn("Preset 1", dados)
        self.assertIn("Preset 2", dados)
        self.assertEqual(dados["Preset 1"], grid1)
        self.assertEqual(dados["Preset 2"], grid2)

    def test_aplicar_predefinicao(self):
        """Test applying a preset loads saved camera IPs into grid slots."""
        preset_ips = ["192.168.7.100", "192.168.7.101", "192.168.7.102"] + ["0.0.0.0"] * 13
        self.app.presets_salvos["Entrada Principal"] = preset_ips

        # Set grid to something else
        self.app.grid_cameras = ["0.0.0.0"] * self.app.MAX_SLOTS
        self.app.aplicar_preset("Entrada Principal")

        self.assertEqual(self.app.grid_cameras, preset_ips)

    def test_renomear_predefinicao(self):
        """Test renaming a preset."""
        preset_ips = ["192.168.7.5"] + ["0.0.0.0"] * 15
        self.app.presets_salvos["Antigo Nome"] = preset_ips
        self.app.salvar_presets()

        self.app._executar_renomear_preset("Antigo Nome", "Novo Nome")

        self.assertNotIn("Antigo Nome", self.app.presets_salvos)
        self.assertIn("Novo Nome", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo Nome"], preset_ips)

        # Verify JSON
        loaded = self.app.carregar_presets()
        self.assertNotIn("Antigo Nome", loaded)
        self.assertIn("Novo Nome", loaded)

    def test_deletar_predefinicao(self):
        """Test deleting a preset."""
        self.app.presets_salvos["Para Deletar"] = ["192.168.7.50"] + ["0.0.0.0"] * 15
        self.app.salvar_presets()

        self.app.excluir_preset("Para Deletar")

        self.assertNotIn("Para Deletar", self.app.presets_salvos)
        loaded = self.app.carregar_presets()
        self.assertNotIn("Para Deletar", loaded)

    def test_preset_labels_referencia(self):
        """Test UI updates populate preset_labels_referencia correctly."""
        self.app.presets_salvos = {
            "Zona A": ["0.0.0.0"] * 16,
            "Zona B": ["0.0.0.0"] * 16
        }
        self.app.atualizar_lista_presets_ui()

        self.assertIn("Zona A", self.app.preset_labels_referencia)
        self.assertIn("Zona B", self.app.preset_labels_referencia)
        self.assertEqual(self.app.preset_labels_referencia["Zona A"].cget("text"), "Zona A")

if __name__ == "__main__":
    unittest.main()
