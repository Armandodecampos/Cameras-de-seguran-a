import os
import json
import unittest
import tempfile
import shutil

import Cameras

class TestPresetManagement(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for config files during testing
        self.temp_dir = tempfile.mkdtemp()

        # Patch CentralMonitoramento file paths to use temp_dir
        self.original_arquivo_presets = Cameras.CentralMonitoramento.carregar_presets

        # We can instantiate CentralMonitoramento with modified file paths
        # To avoid UI blocking loops during unit tests, we override loop_exibicao
        self.original_loop_exibicao = Cameras.CentralMonitoramento.loop_exibicao
        Cameras.CentralMonitoramento.loop_exibicao = lambda self: None

        self.app = Cameras.CentralMonitoramento()
        self.app.arquivo_presets = os.path.join(self.temp_dir, "presets_config_test.json")
        self.app.arquivo_grid = os.path.join(self.temp_dir, "grid_config_test.json")
        self.app.presets_salvos = {}

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        Cameras.CentralMonitoramento.loop_exibicao = self.original_loop_exibicao
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_salvar_preset(self):
        """Test saving a preset configuration."""
        test_grid = ["192.168.7.10", "192.168.7.11"] + ["0.0.0.0"] * 14
        self.app.grid_cameras = list(test_grid)

        preset_name = "Predefinição Teste 1"
        self.app._executar_salvamento_preset(preset_name)

        # Check in memory
        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name], test_grid)

        # Check in JSON file
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn(preset_name, data)
        self.assertEqual(data[preset_name], test_grid)

    def test_renomear_preset(self):
        """Test renaming an existing preset."""
        test_grid = ["192.168.7.10"] + ["0.0.0.0"] * 15
        old_name = "Nome Antigo"
        new_name = "Nome Novo"

        self.app._executar_salvamento_preset(old_name)
        self.assertIn(old_name, self.app.presets_salvos)

        self.app._executar_renomear_preset(old_name, new_name)
        self.assertNotIn(old_name, self.app.presets_salvos)
        self.assertIn(new_name, self.app.presets_salvos)

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn(old_name, data)
        self.assertIn(new_name, data)

    def test_excluir_preset(self):
        """Test deleting a preset."""
        preset_name = "Para Deletar"
        self.app._executar_salvamento_preset(preset_name)
        self.assertIn(preset_name, self.app.presets_salvos)

        self.app.excluir_preset(preset_name)
        self.assertNotIn(preset_name, self.app.presets_salvos)

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn(preset_name, data)

    def test_aplicar_preset(self):
        """Test applying a preset to load all saved cameras into the grid."""
        preset_grid = ["192.168.7.100", "192.168.7.101", "192.168.7.102"] + ["0.0.0.0"] * 13
        preset_name = "Entrada Principal"

        self.app.presets_salvos[preset_name] = preset_grid
        self.app.salvar_presets()

        # Reset current grid
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # Apply preset
        self.app.aplicar_preset(preset_name)

        # Verify grid updated to preset configuration
        self.assertEqual(self.app.grid_cameras, preset_grid)

if __name__ == "__main__":
    unittest.main()
