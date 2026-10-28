import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch

import customtkinter as ctk
import Cameras


class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for config files
        self.test_dir = tempfile.mkdtemp()
        self.preset_file = os.path.join(self.test_dir, "presets_config_abi.json")
        self.grid_file = os.path.join(self.test_dir, "grid_config_abi.json")

        # Instantiate application in headless mode
        with patch.object(Cameras.CentralMonitoramento, 'loop_exibicao', lambda self: None), \
             patch.object(Cameras.CentralMonitoramento, 'alternar_todos_streams', lambda self: None), \
             patch.object(Cameras.CentralMonitoramento, '_processar_fila_conexoes_pendentes', lambda self: None):
            self.app = Cameras.CentralMonitoramento()

        # Override instance file paths to use temp directory
        self.app.arquivo_presets = self.preset_file
        self.app.arquivo_grid = self.grid_file

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_salvar_e_carregar_preset(self):
        """Test saving a camera preset and persisting it to file."""
        test_ips = [f"192.168.7.{10+i}" for i in range(16)]
        self.app.grid_cameras = list(test_ips)

        preset_name = "Turno Manhã"
        self.app._executar_salvamento_preset(preset_name)

        # Verify preset in memory
        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name], test_ips)

        # Verify preset written to JSON
        self.assertTrue(os.path.exists(self.preset_file))
        with open(self.preset_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertIn(preset_name, saved_data)
        self.assertEqual(saved_data[preset_name], test_ips)

    def test_aplicar_preset(self):
        """Test applying a saved preset to update all camera slots."""
        preset_name = "Entradas Principais"
        preset_ips = [f"10.0.0.{i+1}" for i in range(16)]
        self.app.presets_salvos[preset_name] = preset_ips

        # Set current grid to something else
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # Apply preset
        self.app.aplicar_preset(preset_name)

        # Verify grid_cameras updated
        self.assertEqual(self.app.grid_cameras, preset_ips)

        # Verify grid persisted
        with open(self.grid_file, "r", encoding="utf-8") as f:
            grid_data = json.load(f)
        self.assertEqual(grid_data, preset_ips)

    def test_renomear_preset(self):
        """Test renaming an existing preset."""
        old_name = "Setor A"
        new_name = "Setor Norte"
        preset_ips = ["192.168.1.1"] * 16

        self.app.presets_salvos[old_name] = preset_ips
        self.app.salvar_presets()

        self.app._executar_renomear_preset(old_name, new_name)

        # Check in memory
        self.assertNotIn(old_name, self.app.presets_salvos)
        self.assertIn(new_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[new_name], preset_ips)

        # Check in JSON
        with open(self.preset_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertNotIn(old_name, saved_data)
        self.assertIn(new_name, saved_data)

    def test_excluir_preset(self):
        """Test deleting a preset."""
        preset_name = "Predefinição Temp"
        self.app.presets_salvos[preset_name] = ["192.168.1.50"] * 16
        self.app.salvar_presets()

        self.app.excluir_preset(preset_name)

        # Check in memory
        self.assertNotIn(preset_name, self.app.presets_salvos)

        # Check in JSON
        with open(self.preset_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertNotIn(preset_name, saved_data)

    def test_atualizar_lista_presets_ui(self):
        """Test that updating the presets UI renders saved presets in frame_presets."""
        self.app.presets_salvos = {
            "Preset 1": ["192.168.7.1"] * 16,
            "Preset 2": ["192.168.7.2"] * 16
        }

        self.app.atualizar_lista_presets_ui()

        # Ensure widgets were created inside frame_presets
        children = self.app.frame_presets.winfo_children()
        self.assertTrue(len(children) > 0)


if __name__ == "__main__":
    unittest.main()
