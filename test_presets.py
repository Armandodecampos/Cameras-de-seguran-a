import unittest
import os
import json
import shutil
import tempfile
import customtkinter as ctk

# Import CentralMonitoramento
from Cameras import CentralMonitoramento

class TestPresets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctk.set_appearance_mode("Dark")

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.presets_file = os.path.join(self.test_dir, "presets_config_abi.json")
        self.grid_file = os.path.join(self.test_dir, "grid_config_abi.json")
        self.janela_file = os.path.join(self.test_dir, "config_janela_abi.json")
        self.ips_file = os.path.join(self.test_dir, "lista_ips_abi.json")
        self.config_file = os.path.join(self.test_dir, "config_cameras_abi.json")

        self.app = CentralMonitoramento()
        self.app.withdraw()  # Hide GUI window during tests

        # Redirect config paths to test_dir
        self.app.arquivo_presets = self.presets_file
        self.app.arquivo_grid = self.grid_file
        self.app.arquivo_janela = self.janela_file
        self.app.arquivo_ips = self.ips_file
        self.app.arquivo_config = self.config_file

        self.app.presets_salvos = {}

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_salvar_preset_e_persistencia(self):
        # Set dummy grid cameras
        test_grid = ["192.168.7.10", "192.168.7.11"] + ["0.0.0.0"] * 14
        self.app.grid_cameras = list(test_grid)

        # Save preset directly
        self.app._executar_salvamento_preset("Preset Teste 1")

        # Verify memory state
        self.assertIn("Preset Teste 1", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset Teste 1"], test_grid)

        # Verify disk persistence
        self.assertTrue(os.path.exists(self.presets_file))
        with open(self.presets_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("Preset Teste 1", data)
        self.assertEqual(data["Preset Teste 1"], test_grid)

    def test_aplicar_preset(self):
        preset_grid = ["192.168.7.20", "192.168.7.21", "192.168.7.22"] + ["0.0.0.0"] * 13
        self.app.presets_salvos["Preset Especial"] = preset_grid

        # Apply preset
        self.app.aplicar_preset("Preset Especial")

        # Verify grid_cameras updated
        self.assertEqual(self.app.grid_cameras, preset_grid)

    def test_renomear_preset(self):
        preset_grid = ["192.168.7.30"] + ["0.0.0.0"] * 15
        self.app.presets_salvos["Antigo Nome"] = preset_grid

        # Execute rename
        self.app._executar_renomear_preset("Antigo Nome", "Novo Nome")

        # Verify state
        self.assertNotIn("Antigo Nome", self.app.presets_salvos)
        self.assertIn("Novo Nome", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo Nome"], preset_grid)

    def test_excluir_preset(self):
        self.app.presets_salvos["Preset Para Deletar"] = ["0.0.0.0"] * 16
        self.app.excluir_preset("Preset Para Deletar")

        self.assertNotIn("Preset Para Deletar", self.app.presets_salvos)

if __name__ == "__main__":
    unittest.main()
