import unittest
import os
import json
import shutil
import tempfile
import Cameras

class TestPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.app = Cameras.CentralMonitoramento()

        # Redirect file paths to temporary test directory
        self.app.arquivo_presets = os.path.join(self.test_dir, "presets_config_abi.json")
        self.app.arquivo_grid = os.path.join(self.test_dir, "grid_config_abi.json")

        self.app.presets_salvos = {}
        self.app.grid_cameras = ["0.0.0.0"] * self.app.MAX_SLOTS

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_salvar_e_carregar_preset(self):
        # Set dummy camera IPs on the grid
        self.app.grid_cameras[0] = "192.168.7.10"
        self.app.grid_cameras[1] = "192.168.7.20"

        # Save preset programmatically
        self.app.salvar_preset_atual("Preset_1")

        # Check dictionary and JSON file
        self.assertIn("Preset_1", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset_1"][0], "192.168.7.10")
        self.assertEqual(self.app.presets_salvos["Preset_1"][1], "192.168.7.20")

        # Read JSON file directly
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("Preset_1", data)

    def test_aplicar_preset(self):
        preset_grid = ["192.168.7.100", "192.168.7.101"] + ["0.0.0.0"] * 14
        self.app.presets_salvos["Entrada"] = preset_grid

        # Apply preset
        self.app.aplicar_preset("Entrada")

        self.assertEqual(self.app.grid_cameras[0], "192.168.7.100")
        self.assertEqual(self.app.grid_cameras[1], "192.168.7.101")
        for i in range(2, 16):
            self.assertEqual(self.app.grid_cameras[i], "0.0.0.0")

    def test_renomear_preset(self):
        self.app.presets_salvos["Antigo"] = ["192.168.7.5"] + ["0.0.0.0"] * 15
        self.app.salvar_presets()

        self.app._executar_renomear_preset("Antigo", "Novo")

        self.assertNotIn("Antigo", self.app.presets_salvos)
        self.assertIn("Novo", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo"][0], "192.168.7.5")

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn("Antigo", data)
        self.assertIn("Novo", data)

    def test_excluir_preset(self):
        self.app.presets_salvos["ParaDeletar"] = ["192.168.7.8"] + ["0.0.0.0"] * 15
        self.app.salvar_presets()

        self.app.excluir_preset("ParaDeletar")

        self.assertNotIn("ParaDeletar", self.app.presets_salvos)
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn("ParaDeletar", data)

    def test_ui_preset_labels_referencia(self):
        self.app.presets_salvos["Preset_UI_Test"] = ["192.168.7.9"] + ["0.0.0.0"] * 15
        self.app.atualizar_lista_presets_ui()

        self.assertIn("Preset_UI_Test", self.app.preset_labels_referencia)
        lbl = self.app.preset_labels_referencia["Preset_UI_Test"]
        self.assertEqual(lbl.cget("text"), "Preset_UI_Test")

if __name__ == "__main__":
    unittest.main()
