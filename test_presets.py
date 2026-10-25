import unittest
import os
import json
import shutil
import tempfile
import customtkinter as ctk
import Cameras

class TestPresetManagement(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_user_dir = os.path.expanduser("~")

        # Mock home directory to prevent overwriting user config files
        os.path.expanduser = lambda path: self.temp_dir if path == "~" else path

        self.app = Cameras.CentralMonitoramento()

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        os.path.expanduser = os.path.expanduser
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_preset(self):
        # Set up grid cameras
        self.app.grid_cameras[0] = "192.168.7.10"
        self.app.grid_cameras[1] = "192.168.7.11"

        self.app._executar_salvamento_preset("Entrada e Garagem")
        self.assertIn("Entrada e Garagem", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Entrada e Garagem"][0], "192.168.7.10")
        self.assertEqual(self.app.presets_salvos["Entrada e Garagem"][1], "192.168.7.11")

        # Verify file persistence
        file_path = os.path.join(self.temp_dir, "presets_config_abi.json")
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("Entrada e Garagem", data)

    def test_apply_preset(self):
        # Save preset A
        self.app.grid_cameras[0] = "192.168.7.20"
        self.app.grid_cameras[1] = "192.168.7.21"
        self.app._executar_salvamento_preset("Preset A")

        # Clear grid
        for i in range(self.app.MAX_SLOTS):
            self.app.grid_cameras[i] = "0.0.0.0"

        # Apply preset A
        self.app.aplicar_preset("Preset A")
        self.assertEqual(self.app.grid_cameras[0], "192.168.7.20")
        self.assertEqual(self.app.grid_cameras[1], "192.168.7.21")

    def test_rename_preset(self):
        self.app.grid_cameras[0] = "192.168.7.30"
        self.app._executar_salvamento_preset("Nome Antigo")

        self.app._executar_renomear_preset("Nome Antigo", "Nome Novo")
        self.assertNotIn("Nome Antigo", self.app.presets_salvos)
        self.assertIn("Nome Novo", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Nome Novo"][0], "192.168.7.30")

    def test_delete_preset(self):
        self.app.grid_cameras[0] = "192.168.7.40"
        self.app._executar_salvamento_preset("Para Excluir")
        self.assertIn("Para Excluir", self.app.presets_salvos)

        self.app.excluir_preset("Para Excluir")
        self.assertNotIn("Para Excluir", self.app.presets_salvos)

    def test_preset_ui_references(self):
        self.app.grid_cameras[0] = "192.168.7.50"
        self.app._executar_salvamento_preset("Preset UI Test")
        self.app.atualizar_lista_presets_ui()

        self.assertIn("Preset UI Test", self.app.preset_labels_referencia)
        lbl = self.app.preset_labels_referencia["Preset UI Test"]
        self.assertIsInstance(lbl, ctk.CTkLabel)

if __name__ == "__main__":
    unittest.main()
