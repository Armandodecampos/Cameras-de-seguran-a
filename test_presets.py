import unittest
import os
import json
import customtkinter as ctk
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.app = CentralMonitoramento()

    def tearDown(self):
        self.app.destroy()

    def test_preset_saving_and_loading(self):
        # Set a test grid layout
        test_grid = ["192.168.7.2", "192.168.7.3", "192.168.7.4"] + ["0.0.0.0"] * 13
        self.app.grid_cameras = list(test_grid)

        # Save preset
        preset_name = "Preset Entrada"
        self.app._executar_salvamento_preset(preset_name)
        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name], test_grid)

        # Clear grid and apply preset
        self.app.grid_cameras = ["0.0.0.0"] * 16
        self.app.aplicar_preset(preset_name)
        self.assertEqual(self.app.grid_cameras, test_grid)

    def test_preset_renaming(self):
        # Save initial preset
        initial_name = "Preset Antigo"
        new_name = "Preset Novo"
        test_grid = ["192.168.7.20"] + ["0.0.0.0"] * 15
        self.app.grid_cameras = list(test_grid)
        self.app._executar_salvamento_preset(initial_name)

        # Rename preset
        self.app._executar_renomear_preset(initial_name, new_name)
        self.assertNotIn(initial_name, self.app.presets_salvos)
        self.assertIn(new_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[new_name], test_grid)

    def test_preset_deletion(self):
        # Save preset
        preset_name = "Preset Deletar"
        self.app._executar_salvamento_preset(preset_name)
        self.assertIn(preset_name, self.app.presets_salvos)

        # Delete preset
        self.app.excluir_preset(preset_name)
        self.assertNotIn(preset_name, self.app.presets_salvos)

    def test_file_persistence(self):
        preset_name = "Preset Persistencia"
        test_grid = ["192.168.7.50"] + ["0.0.0.0"] * 15
        self.app.grid_cameras = list(test_grid)
        self.app._executar_salvamento_preset(preset_name)

        # Verify JSON file
        self.assertTrue(os.path.exists(self.app.arquivo_presets))
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn(preset_name, data)
            self.assertEqual(data[preset_name], test_grid)

        # Clean up preset from app and file
        self.app.excluir_preset(preset_name)

if __name__ == "__main__":
    unittest.main()
