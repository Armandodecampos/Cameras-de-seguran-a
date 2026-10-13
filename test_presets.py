import unittest
import os
import json
import shutil
import tempfile
import customtkinter as ctk
from Cameras import CentralMonitoramento

class TestPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.app = CentralMonitoramento()
        self.app.withdraw() # Hide window during test execution

        # Override config files to use temporary directory
        self.app.arquivo_presets = os.path.join(self.test_dir, "presets_config_test.json")
        self.app.arquivo_grid = os.path.join(self.test_dir, "grid_config_test.json")
        self.app.presets_salvos = {}

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_salvar_preset(self):
        self.app.grid_cameras[0] = "192.168.7.10"
        self.app.grid_cameras[1] = "192.168.7.20"

        self.app._executar_salvamento_preset("Preset 1")

        self.assertIn("Preset 1", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset 1"][0], "192.168.7.10")
        self.assertEqual(self.app.presets_salvos["Preset 1"][1], "192.168.7.20")

        # Verify file persistence
        self.assertTrue(os.path.exists(self.app.arquivo_presets))
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("Preset 1", data)

    def test_aplicar_preset(self):
        preset_ips = ["0.0.0.0"] * self.app.MAX_SLOTS
        preset_ips[0] = "192.168.7.100"
        preset_ips[3] = "192.168.7.103"
        self.app.presets_salvos["Preset Teste"] = preset_ips

        self.app.aplicar_preset("Preset Teste")

        self.assertEqual(self.app.grid_cameras[0], "192.168.7.100")
        self.assertEqual(self.app.grid_cameras[3], "192.168.7.103")

    def test_renomear_preset(self):
        self.app.presets_salvos["Antigo"] = ["192.168.7.1"] * self.app.MAX_SLOTS
        self.app._executar_renomear_preset("Antigo", "Novo")

        self.assertNotIn("Antigo", self.app.presets_salvos)
        self.assertIn("Novo", self.app.presets_salvos)
        self.assertEqual(len(self.app.presets_salvos["Novo"]), self.app.MAX_SLOTS)

    def test_excluir_preset(self):
        self.app.presets_salvos["ParaDeletar"] = ["0.0.0.0"] * self.app.MAX_SLOTS
        self.app.excluir_preset("ParaDeletar")

        self.assertNotIn("ParaDeletar", self.app.presets_salvos)

    def test_preset_ui_references(self):
        self.app.presets_salvos["UI Preset"] = ["0.0.0.0"] * self.app.MAX_SLOTS
        self.app.atualizar_lista_presets_ui()

        self.assertIn("UI Preset", self.app.preset_labels_referencia)
        lbl = self.app.preset_labels_referencia["UI Preset"]
        self.assertIsInstance(lbl, ctk.CTkLabel)

if __name__ == "__main__":
    unittest.main()
