import unittest
import os
import json
import shutil
import tempfile
import customtkinter as ctk

import Cameras


class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.preset_file = os.path.join(self.temp_dir, "presets_config_abi.json")
        self.grid_file = os.path.join(self.temp_dir, "grid_config_abi.json")

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_preset_save_load_rename_delete(self):
        app = Cameras.CentralMonitoramento()
        app.arquivo_presets = self.preset_file
        app.arquivo_grid = self.grid_file

        # 1. Save Preset
        test_grid_1 = ["192.168.7.2", "192.168.7.3"] + ["0.0.0.0"] * 14
        app.grid_cameras = list(test_grid_1)
        app._executar_salvamento_preset("Preset Entrada")

        self.assertIn("Preset Entrada", app.presets_salvos)
        self.assertEqual(app.presets_salvos["Preset Entrada"], test_grid_1)

        # Verify file persistence
        with open(self.preset_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("Preset Entrada", data)

        # 2. Save Second Preset
        test_grid_2 = ["192.168.7.20", "192.168.7.21", "192.168.7.22"] + ["0.0.0.0"] * 13
        app.grid_cameras = list(test_grid_2)
        app._executar_salvamento_preset("Preset Saida")

        self.assertIn("Preset Saida", app.presets_salvos)

        # 3. Apply First Preset
        app.aplicar_preset("Preset Entrada")
        self.assertEqual(app.grid_cameras, test_grid_1)

        # 4. Rename Preset
        app._executar_renomear_preset("Preset Entrada", "Preset Principal")
        self.assertNotIn("Preset Entrada", app.presets_salvos)
        self.assertIn("Preset Principal", app.presets_salvos)
        self.assertEqual(app.presets_salvos["Preset Principal"], test_grid_1)

        # 5. Delete Preset
        app.excluir_preset("Preset Saida")
        self.assertNotIn("Preset Saida", app.presets_salvos)

        app.destroy()


if __name__ == "__main__":
    unittest.main()
