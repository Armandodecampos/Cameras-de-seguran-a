import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import MagicMock, patch

# Ensure CustomTkinter runs headlessly if needed
import customtkinter as ctk
ctk.set_appearance_mode("Dark")

from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.patcher_home = patch("os.path.expanduser", return_value=self.test_dir)
        self.mock_home = self.patcher_home.start()

        # Instantiate app
        self.app = CentralMonitoramento()

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        self.patcher_home.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_salvar_e_carregar_presets(self):
        # Set up grid cameras
        sample_grid = ["192.168.7.10", "192.168.7.11", "0.0.0.0", "192.168.7.12"] + ["0.0.0.0"] * 12
        self.app.grid_cameras = list(sample_grid)

        # Save preset
        preset_name = "Monitoramento Noturno"
        self.app._executar_salvamento_preset(preset_name)

        # Check in memory dictionary
        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name], sample_grid)

        # Check saved JSON file
        preset_file = os.path.join(self.test_dir, "presets_config_abi.json")
        self.assertTrue(os.path.exists(preset_file))
        with open(preset_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn(preset_name, data)
        self.assertEqual(data[preset_name], sample_grid)

    def test_aplicar_preset(self):
        # Save two different presets
        preset_a = ["192.168.7.100"] * 16
        preset_b = ["192.168.7.200"] * 16
        self.app.presets_salvos["Preset A"] = preset_a
        self.app.presets_salvos["Preset B"] = preset_b
        self.app.salvar_presets()

        # Apply Preset A
        self.app.aplicar_preset("Preset A")
        self.assertEqual(self.app.grid_cameras, preset_a)

        # Apply Preset B
        self.app.aplicar_preset("Preset B")
        self.assertEqual(self.app.grid_cameras, preset_b)

    def test_renomear_preset(self):
        preset_orig = "Entrada Principal"
        preset_novo = "Portao Frente"
        sample_grid = ["192.168.7.50"] + ["0.0.0.0"] * 15

        self.app.presets_salvos[preset_orig] = sample_grid
        self.app.salvar_presets()

        # Execute rename
        self.app._executar_renomear_preset(preset_orig, preset_novo)

        # Confirm old key is gone, new key exists
        self.assertNotIn(preset_orig, self.app.presets_salvos)
        self.assertIn(preset_novo, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_novo], sample_grid)

        # Check persistent storage
        preset_file = os.path.join(self.test_dir, "presets_config_abi.json")
        with open(preset_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn(preset_orig, data)
        self.assertIn(preset_novo, data)

    def test_excluir_preset(self):
        preset_name = "Preset Para Deletar"
        self.app.presets_salvos[preset_name] = ["0.0.0.0"] * 16
        self.app.salvar_presets()

        self.assertIn(preset_name, self.app.presets_salvos)

        # Delete preset
        self.app.excluir_preset(preset_name)

        self.assertNotIn(preset_name, self.app.presets_salvos)
        preset_file = os.path.join(self.test_dir, "presets_config_abi.json")
        with open(preset_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn(preset_name, data)

    def test_preset_ui_references(self):
        self.app.presets_salvos["Preset UI 1"] = ["0.0.0.0"] * 16
        self.app.presets_salvos["Preset UI 2"] = ["0.0.0.0"] * 16
        self.app.atualizar_lista_presets_ui()

        self.assertIn("Preset UI 1", self.app.preset_labels_referencia)
        self.assertIn("Preset UI 2", self.app.preset_labels_referencia)

if __name__ == "__main__":
    unittest.main()
