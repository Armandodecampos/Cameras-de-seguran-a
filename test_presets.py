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
        # Patch expanduser so files go to temp_dir
        self.orig_expanduser = os.path.expanduser
        os.path.expanduser = lambda path="~": self.temp_dir
        self.app = Cameras.CentralMonitoramento()

    def tearDown(self):
        os.path.expanduser = self.orig_expanduser
        try:
            self.app.destroy()
        except Exception:
            pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_load_preset(self):
        # Set specific IPs in slots
        self.app.grid_cameras[0] = "192.168.7.10"
        self.app.grid_cameras[1] = "192.168.7.20"

        # Save preset
        preset_name = "Preset Test 1"
        self.app._executar_salvamento_preset(preset_name)

        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name][0], "192.168.7.10")
        self.assertEqual(self.app.presets_salvos[preset_name][1], "192.168.7.20")

        # Verify JSON file persistence
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn(preset_name, data)

    def test_apply_preset(self):
        preset_name = "Setores"
        sample_grid = ["0.0.0.0"] * 16
        sample_grid[0] = "192.168.7.30"
        sample_grid[3] = "192.168.7.40"
        self.app.presets_salvos[preset_name] = sample_grid

        # Reset current grid
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # Apply preset
        self.app.aplicar_preset(preset_name)

        self.assertEqual(self.app.grid_cameras[0], "192.168.7.30")
        self.assertEqual(self.app.grid_cameras[3], "192.168.7.40")

    def test_rename_preset(self):
        old_name = "Old Preset"
        new_name = "New Preset"
        self.app.presets_salvos[old_name] = ["192.168.7.2"] + ["0.0.0.0"] * 15

        self.app._executar_renomear_preset(old_name, new_name)

        self.assertNotIn(old_name, self.app.presets_salvos)
        self.assertIn(new_name, self.app.presets_salvos)

    def test_delete_preset(self):
        preset_name = "ToDelete"
        self.app.presets_salvos[preset_name] = ["0.0.0.0"] * 16

        self.app.excluir_preset(preset_name)

        self.assertNotIn(preset_name, self.app.presets_salvos)

    def test_preset_ui_references(self):
        self.app._executar_salvamento_preset("UI Preset")
        self.app.mudar_aba_sidebar("Predefinições")
        self.app.atualizar_lista_presets_ui()

        self.assertIn("UI Preset", self.app.preset_labels_referencia)
        self.assertTrue(self.app.preset_labels_referencia["UI Preset"].winfo_exists())

if __name__ == "__main__":
    unittest.main()
