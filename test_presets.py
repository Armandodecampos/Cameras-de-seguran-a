import unittest
import os
import json
import shutil
import tempfile
import customtkinter as ctk
import Cameras

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test config files
        self.test_dir = tempfile.mkdtemp()
        self.preset_file = os.path.join(self.test_dir, "presets_config_abi.json")
        self.grid_file = os.path.join(self.test_dir, "grid_config_abi.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_preset_lifecycle(self):
        app = Cameras.CentralMonitoramento()
        app.arquivo_presets = self.preset_file
        app.arquivo_grid = self.grid_file
        app.presets_salvos = {}

        # 1. Setup initial camera grid layout
        app.grid_cameras = ["0.0.0.0"] * app.MAX_SLOTS
        app.grid_cameras[0] = "192.168.7.10"
        app.grid_cameras[1] = "192.168.7.11"
        app.grid_cameras[2] = "192.168.7.12"

        # 2. Save multiple presets
        app._executar_salvamento_preset("Entrada")

        app.grid_cameras[0] = "192.168.7.20"
        app.grid_cameras[1] = "192.168.7.21"
        app._executar_salvamento_preset("Patio")

        self.assertIn("Entrada", app.presets_salvos)
        self.assertIn("Patio", app.presets_salvos)
        self.assertEqual(app.presets_salvos["Entrada"][0], "192.168.7.10")
        self.assertEqual(app.presets_salvos["Patio"][0], "192.168.7.20")

        # Check persistence file
        self.assertTrue(os.path.exists(self.preset_file))
        with open(self.preset_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("Entrada", data)
            self.assertIn("Patio", data)

        # 3. Apply preset "Entrada"
        app.aplicar_preset("Entrada")
        self.assertEqual(app.grid_cameras[0], "192.168.7.10")
        self.assertEqual(app.grid_cameras[1], "192.168.7.11")
        self.assertEqual(app.grid_cameras[2], "192.168.7.12")

        # 4. Rename preset
        app._executar_renomear_preset("Entrada", "Entrada Principal")
        self.assertNotIn("Entrada", app.presets_salvos)
        self.assertIn("Entrada Principal", app.presets_salvos)
        self.assertEqual(app.presets_salvos["Entrada Principal"][0], "192.168.7.10")

        # Check persistence after rename
        with open(self.preset_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertNotIn("Entrada", data)
            self.assertIn("Entrada Principal", data)

        # 5. Delete preset
        app.excluir_preset("Patio")
        self.assertNotIn("Patio", app.presets_salvos)

        with open(self.preset_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertNotIn("Patio", data)

        # 6. Verify UI widgets in presets tab
        app.mudar_aba_sidebar("Predefinições")
        app.atualizar_lista_presets_ui()

        # Check that UI components exist in frame_presets
        children = app.frame_presets.winfo_children()
        self.assertTrue(len(children) > 0)

        app.destroy()

if __name__ == "__main__":
    unittest.main()
