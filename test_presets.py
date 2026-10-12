import unittest
import os
import json
import tempfile
import shutil
import Cameras

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.presets_file = os.path.join(self.test_dir, "presets_config_abi.json")
        self.grid_file = os.path.join(self.test_dir, "grid_config_abi.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_rename_apply_delete_preset(self):
        app = Cameras.CentralMonitoramento()
        app.arquivo_presets = self.presets_file
        app.arquivo_grid = self.grid_file

        # Set up a test grid configuration
        test_ips = ["192.168.7.10", "192.168.7.11", "192.168.7.12"] + ["0.0.0.0"] * 13
        app.grid_cameras = list(test_ips)

        # 1. Test Saving Preset
        app._executar_salvamento_preset("Entrada e Estacionamento")
        self.assertIn("Entrada e Estacionamento", app.presets_salvos)
        self.assertEqual(app.presets_salvos["Entrada e Estacionamento"][:3], ["192.168.7.10", "192.168.7.11", "192.168.7.12"])

        # Verify disk persistence
        with open(self.presets_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertIn("Entrada e Estacionamento", saved_data)

        # 2. Test Renaming Preset
        app._executar_renomear_preset("Entrada e Estacionamento", "Setor A")
        self.assertNotIn("Entrada e Estacionamento", app.presets_salvos)
        self.assertIn("Setor A", app.presets_salvos)

        with open(self.presets_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertNotIn("Entrada e Estacionamento", saved_data)
        self.assertIn("Setor A", saved_data)

        # 3. Test Applying Preset
        # Reset grid to empty
        app.grid_cameras = ["0.0.0.0"] * 16
        app.aplicar_preset("Setor A")
        self.assertEqual(app.grid_cameras[:3], ["192.168.7.10", "192.168.7.11", "192.168.7.12"])

        # 4. Test Deleting Preset
        app.excluir_preset("Setor A")
        self.assertNotIn("Setor A", app.presets_salvos)

        with open(self.presets_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertNotIn("Setor A", saved_data)

        app.destroy()

if __name__ == '__main__':
    unittest.main()
