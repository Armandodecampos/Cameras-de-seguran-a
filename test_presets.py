import unittest
import os
import json
import tempfile
import customtkinter as ctk
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patcher_home = os.environ.get("HOME")
        os.environ["HOME"] = self.temp_dir.name

    def tearDown(self):
        if self.patcher_home:
            os.environ["HOME"] = self.patcher_home
        self.temp_dir.cleanup()

    def test_preset_full_lifecycle_and_ui(self):
        app = CentralMonitoramento()

        # Initial presets should be empty dictionary
        self.assertEqual(app.presets_salvos, {})

        # Set up grid cameras
        app.grid_cameras[0] = "192.168.7.10"
        app.grid_cameras[1] = "192.168.7.11"
        app.grid_cameras[2] = "192.168.7.12"
        for i in range(3, app.MAX_SLOTS):
            app.grid_cameras[i] = "0.0.0.0"

        # 1. Save preset
        preset_name = "Visao Entrada"
        app._executar_salvamento_preset(preset_name)
        self.assertIn(preset_name, app.presets_salvos)
        self.assertEqual(app.presets_salvos[preset_name][0], "192.168.7.10")
        self.assertEqual(app.presets_salvos[preset_name][1], "192.168.7.11")
        self.assertEqual(app.presets_salvos[preset_name][2], "192.168.7.12")

        # Verify JSON file persistence
        presets_filepath = os.path.join(self.temp_dir.name, "presets_config_abi.json")
        self.assertTrue(os.path.exists(presets_filepath))
        with open(presets_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn(preset_name, data)

        # 2. Switch sidebar tab to Predefinições and check UI elements
        app.mudar_aba_sidebar("Predefinições")
        self.assertEqual(app.aba_ativa, "Predefinições")
        self.assertEqual(app.tab_var.get(), "Predefinições")

        # Frame presets should have children (+ button and scroll frame)
        children = app.frame_presets.winfo_children()
        self.assertTrue(len(children) >= 2)

        # 3. Reset grid cameras to empty
        for i in range(app.MAX_SLOTS):
            app.atribuir_ip_ao_slot(i, "0.0.0.0", atualizar_ui=False, gerenciar_conexoes=False, salvar=False)

        self.assertEqual(app.grid_cameras[0], "0.0.0.0")

        # 4. Apply preset and verify all saved cameras are loaded
        app.aplicar_preset(preset_name)
        self.assertEqual(app.grid_cameras[0], "192.168.7.10")
        self.assertEqual(app.grid_cameras[1], "192.168.7.11")
        self.assertEqual(app.grid_cameras[2], "192.168.7.12")

        # 5. Rename preset
        new_preset_name = "Visao Portao"
        app._executar_renomear_preset(preset_name, new_preset_name)
        self.assertNotIn(preset_name, app.presets_salvos)
        self.assertIn(new_preset_name, app.presets_salvos)

        # Verify persistence after rename
        with open(presets_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn(new_preset_name, data)
            self.assertNotIn(preset_name, data)

        # 6. Delete preset
        app.excluir_preset(new_preset_name)
        self.assertNotIn(new_preset_name, app.presets_salvos)

        # Verify persistence after deletion
        with open(presets_filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertNotIn(new_preset_name, data)

        app.destroy()

if __name__ == "__main__":
    unittest.main()
