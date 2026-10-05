import unittest
import os
import json
import shutil
import tempfile
import customtkinter as ctk
from Cameras import CentralMonitoramento

class TestPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.patch_files()
        self.app = CentralMonitoramento()
        self.app.withdraw()

    def patch_files(self):
        self.original_presets_file = os.path.join(self.temp_dir, "presets_config_abi.json")
        self.original_grid_file = os.path.join(self.temp_dir, "grid_config_abi.json")

        # Override file paths on CentralMonitoramento prototype or instance in test methods

    def tearDown(self):
        self.app.destroy()
        shutil.rmtree(self.temp_dir)

    def test_salvar_e_carregar_presets(self):
        self.app.arquivo_presets = os.path.join(self.temp_dir, "presets.json")
        self.app.presets_salvos = {}

        # Simula grid com câmeras
        test_grid = ["192.168.7.10", "192.168.7.11"] + ["0.0.0.0"] * 14
        self.app.grid_cameras = list(test_grid)

        # Executa salvamento
        self.app._executar_salvamento_preset("Preset Entrada")
        self.assertIn("Preset Entrada", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset Entrada"][:2], ["192.168.7.10", "192.168.7.11"])

        # Verifica persistência no arquivo JSON
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertIn("Preset Entrada", saved_data)

    def test_aplicar_preset(self):
        self.app.presets_salvos = {
            "Preset Saida": ["192.168.7.50", "192.168.7.51"] + ["0.0.0.0"] * 14
        }
        self.app.grid_cameras = ["0.0.0.0"] * 16

        self.app.aplicar_preset("Preset Saida")
        self.assertEqual(self.app.grid_cameras[0], "192.168.7.50")
        self.assertEqual(self.app.grid_cameras[1], "192.168.7.51")

    def test_renomear_preset(self):
        self.app.arquivo_presets = os.path.join(self.temp_dir, "presets.json")
        self.app.presets_salvos = {
            "Antigo Nome": ["192.168.7.1"] + ["0.0.0.0"] * 15
        }

        self.app._executar_renomear_preset("Antigo Nome", "Novo Nome")
        self.assertNotIn("Antigo Nome", self.app.presets_salvos)
        self.assertIn("Novo Nome", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo Nome"][0], "192.168.7.1")

    def test_excluir_preset(self):
        self.app.arquivo_presets = os.path.join(self.temp_dir, "presets.json")
        self.app.presets_salvos = {
            "Preset Para Deletar": ["192.168.7.1"] + ["0.0.0.0"] * 15
        }

        self.app.excluir_preset("Preset Para Deletar")
        self.assertNotIn("Preset Para Deletar", self.app.presets_salvos)

if __name__ == "__main__":
    unittest.main()
