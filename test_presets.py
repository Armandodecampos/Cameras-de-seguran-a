import unittest
import os
import json
import shutil
import tempfile
import customtkinter as ctk
from unittest.mock import MagicMock, patch

import Cameras

class TestPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.presets_file = os.path.join(self.test_dir, "presets_config_abi.json")
        self.grid_file = os.path.join(self.test_dir, "grid_config_abi.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch.object(Cameras.CentralMonitoramento, 'loop_exibicao', lambda self: None)
    @patch.object(Cameras.CentralMonitoramento, 'alternar_todos_streams', lambda self: None)
    def test_salvar_aplicar_renomear_deletar_presets(self):
        with patch("os.path.expanduser", return_value=self.test_dir):
            app = Cameras.CentralMonitoramento()
            app.withdraw()

            # Set test camera grid
            app.grid_cameras = ["192.168.7.10"] + ["0.0.0.0"] * 15

            # Save preset
            app._executar_salvamento_preset("Preset 1")
            self.assertIn("Preset 1", app.presets_salvos)
            self.assertEqual(app.presets_salvos["Preset 1"][0], "192.168.7.10")

            # Verify persistent JSON file
            self.assertTrue(os.path.exists(app.arquivo_presets))
            with open(app.arquivo_presets, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            self.assertIn("Preset 1", saved_data)

            # Change grid and apply preset
            app.grid_cameras = ["0.0.0.0"] * 16
            app.aplicar_preset("Preset 1")
            self.assertEqual(app.grid_cameras[0], "192.168.7.10")

            # Rename preset
            app._executar_renomear_preset("Preset 1", "Preset Renomeado")
            self.assertNotIn("Preset 1", app.presets_salvos)
            self.assertIn("Preset Renomeado", app.presets_salvos)

            # Verify UI reference stored
            self.assertIn("Preset Renomeado", app.preset_labels_referencia)

            # Delete preset
            app.excluir_preset("Preset Renomeado")
            self.assertNotIn("Preset Renomeado", app.presets_salvos)

            app.destroy()

if __name__ == "__main__":
    unittest.main()
