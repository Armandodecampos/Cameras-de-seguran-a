import unittest
import os
import json
import shutil
import tempfile
import Cameras

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.arquivo_presets_test = os.path.join(self.test_dir, "presets_test.json")
        self.arquivo_grid_test = os.path.join(self.test_dir, "grid_test.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_load_rename_delete_presets(self):
        app = Cameras.CentralMonitoramento()
        app.arquivo_presets = self.arquivo_presets_test
        app.arquivo_grid = self.arquivo_grid_test

        # Set specific camera grid configuration
        test_grid = ["192.168.7.10", "192.168.7.11"] + ["0.0.0.0"] * 14
        app.grid_cameras = list(test_grid)

        # 1. Save Preset
        app._executar_salvamento_preset("Entrada Principal")
        self.assertIn("Entrada Principal", app.presets_salvos)
        self.assertEqual(app.presets_salvos["Entrada Principal"], test_grid)

        # Verify file persistence
        with open(self.arquivo_presets_test, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data["Entrada Principal"], test_grid)

        # 2. Modify grid and Apply Preset
        app.grid_cameras = ["0.0.0.0"] * 16
        app.aplicar_preset("Entrada Principal")
        self.assertEqual(app.grid_cameras, test_grid)

        # 3. Rename Preset
        app._executar_renomear_preset("Entrada Principal", "Portaria ZS")
        self.assertNotIn("Entrada Principal", app.presets_salvos)
        self.assertIn("Portaria ZS", app.presets_salvos)
        self.assertEqual(app.presets_salvos["Portaria ZS"], test_grid)

        # 4. Delete Preset
        app.excluir_preset("Portaria ZS")
        self.assertNotIn("Portaria ZS", app.presets_salvos)

        app.destroy()

if __name__ == "__main__":
    unittest.main()
