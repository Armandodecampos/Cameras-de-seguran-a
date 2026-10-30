import unittest
import os
import json
import tempfile
import shutil
import customtkinter as ctk

# Ensure headless operation for CustomTkinter/Tkinter if needed
import Cameras

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

        # Patch files in CentralMonitoramento to test_dir
        self.patcher_user_dir = tempfile.mkdtemp()

        # We can test CentralMonitoramento instance with mocked file paths
        self.app = Cameras.CentralMonitoramento()
        self.app.withdraw() # Hide window during test

        # Override file paths
        self.app.arquivo_presets = os.path.join(self.test_dir, "presets_config_abi.json")
        self.app.arquivo_grid = os.path.join(self.test_dir, "grid_config_abi.json")
        self.app.presets_salvos = {}

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.patcher_user_dir, ignore_errors=True)

    def test_salvar_e_carregar_presets(self):
        # Set up a grid configuration
        self.app.grid_cameras = ["192.168.1.10", "192.168.1.11", "0.0.0.0", "0.0.0.0"] + ["0.0.0.0"] * 12

        # Save preset 'Setor A'
        self.app._executar_salvamento_preset("Setor A")
        self.assertIn("Setor A", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Setor A"][:2], ["192.168.1.10", "192.168.1.11"])

        # Change grid and save preset 'Setor B'
        self.app.grid_cameras = ["192.168.1.20", "192.168.1.21", "192.168.1.22", "0.0.0.0"] + ["0.0.0.0"] * 12
        self.app._executar_salvamento_preset("Setor B")
        self.assertIn("Setor B", self.app.presets_salvos)

        # Verify persistence on disk
        self.assertTrue(os.path.exists(self.app.arquivo_presets))
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertIn("Setor A", dados)
        self.assertIn("Setor B", dados)

    def test_aplicar_preset(self):
        # Setup presets
        self.app.presets_salvos = {
            "Entrada": ["10.0.0.1", "10.0.0.2"] + ["0.0.0.0"] * 14,
            "Galpão": ["10.0.0.10", "10.0.0.11", "10.0.0.12"] + ["0.0.0.0"] * 13
        }

        # Apply 'Entrada'
        self.app.aplicar_preset("Entrada")
        self.assertEqual(self.app.grid_cameras[0], "10.0.0.1")
        self.assertEqual(self.app.grid_cameras[1], "10.0.0.2")

        # Apply 'Galpão'
        self.app.aplicar_preset("Galpão")
        self.assertEqual(self.app.grid_cameras[0], "10.0.0.10")
        self.assertEqual(self.app.grid_cameras[1], "10.0.0.11")
        self.assertEqual(self.app.grid_cameras[2], "10.0.0.12")

    def test_renomear_preset(self):
        self.app.presets_salvos = {
            "Antigo Nome": ["192.168.0.1"] + ["0.0.0.0"] * 15
        }
        self.app.salvar_presets()

        self.app._executar_renomear_preset("Antigo Nome", "Novo Nome")

        self.assertNotIn("Antigo Nome", self.app.presets_salvos)
        self.assertIn("Novo Nome", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo Nome"][0], "192.168.0.1")

    def test_excluir_preset(self):
        self.app.presets_salvos = {
            "Preset 1": ["192.168.0.1"] + ["0.0.0.0"] * 15,
            "Preset 2": ["192.168.0.2"] + ["0.0.0.0"] * 15
        }
        self.app.salvar_presets()

        self.app.excluir_preset("Preset 1")
        self.assertNotIn("Preset 1", self.app.presets_salvos)
        self.assertIn("Preset 2", self.app.presets_salvos)

if __name__ == "__main__":
    unittest.main()
