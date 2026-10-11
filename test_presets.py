import unittest
import os
import tempfile
import json
import customtkinter as ctk
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.presets_file = os.path.join(self.temp_dir.name, "presets_config_abi.json")
        self.grid_file = os.path.join(self.temp_dir.name, "grid_config_abi.json")

        self.app = CentralMonitoramento()
        self.app.arquivo_presets = self.presets_file
        self.app.arquivo_grid = self.grid_file
        self.app.presets_salvos = {}

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        self.temp_dir.cleanup()

    def test_salvar_preset(self):
        self.app.grid_cameras = ["192.168.7.2", "192.168.7.3"] + ["0.0.0.0"] * 14
        self.app._executar_salvamento_preset("Preset 1")

        self.assertIn("Preset 1", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset 1"][:2], ["192.168.7.2", "192.168.7.3"])
        self.assertEqual(len(self.app.presets_salvos["Preset 1"]), 16)

    def test_aplicar_preset(self):
        self.app.presets_salvos["Preset 2"] = ["192.168.7.10", "192.168.7.20"] + ["0.0.0.0"] * 14
        self.app.grid_cameras = ["0.0.0.0"] * 16

        self.app.aplicar_preset("Preset 2")
        self.assertEqual(self.app.grid_cameras[:2], ["192.168.7.10", "192.168.7.20"])

    def test_renomear_preset(self):
        self.app.presets_salvos["Original"] = ["192.168.7.5"] + ["0.0.0.0"] * 15
        self.app._executar_renomear_preset("Original", "Renomeado")

        self.assertNotIn("Original", self.app.presets_salvos)
        self.assertIn("Renomeado", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Renomeado"][0], "192.168.7.5")

    def test_excluir_preset(self):
        self.app.presets_salvos["ParaDeletar"] = ["192.168.7.1"] + ["0.0.0.0"] * 15
        self.app.excluir_preset("ParaDeletar")

        self.assertNotIn("ParaDeletar", self.app.presets_salvos)

    def test_persistencia_json(self):
        self.app.grid_cameras = ["192.168.7.99"] + ["0.0.0.0"] * 15
        self.app._executar_salvamento_preset("Persistente")

        self.assertTrue(os.path.exists(self.presets_file))
        with open(self.presets_file, "r", encoding="utf-8") as f:
            dados = json.load(f)

        self.assertIn("Persistente", dados)
        self.assertEqual(dados["Persistente"][0], "192.168.7.99")

if __name__ == "__main__":
    unittest.main()
