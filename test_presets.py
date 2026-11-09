import unittest
import os
import json
import tempfile
import shutil
import Cameras

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_expanduser = os.path.expanduser
        os.path.expanduser = lambda path: self.temp_dir

        self.app = Cameras.CentralMonitoramento()
        self.app.withdraw()

    def tearDown(self):
        try:
            self.app.destroy()
        except:
            pass
        os.path.expanduser = self.orig_expanduser
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_multiple_presets(self):
        preset_1_ips = [f"192.168.7.{i+1}" for i in range(16)]
        self.app.grid_cameras = list(preset_1_ips)
        self.app.salvar_preset_atual("Preset A")

        self.assertIn("Preset A", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset A"], preset_1_ips)
        self.assertEqual(self.app.preset_ativo, "Preset A")

        preset_2_ips = [f"192.168.7.{i+50}" for i in range(16)]
        self.app.grid_cameras = list(preset_2_ips)
        self.app.salvar_preset_atual("Preset B")

        self.assertIn("Preset B", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset B"], preset_2_ips)
        self.assertEqual(self.app.preset_ativo, "Preset B")

        # Persistence check
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            persisted_data = json.load(f)
        self.assertIn("Preset A", persisted_data)
        self.assertIn("Preset B", persisted_data)
        self.assertEqual(persisted_data["Preset A"], preset_1_ips)
        self.assertEqual(persisted_data["Preset B"], preset_2_ips)

    def test_apply_preset(self):
        preset_ips = [f"192.168.7.{i+20}" for i in range(16)]
        self.app.grid_cameras = list(preset_ips)
        self.app.salvar_preset_atual("Turno Manhã")

        # Clear grid
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # Apply preset
        self.app.aplicar_preset("Turno Manhã")
        self.assertEqual(self.app.grid_cameras, preset_ips)
        self.assertEqual(self.app.preset_ativo, "Turno Manhã")

    def test_rename_preset(self):
        preset_ips = [f"192.168.7.{i+30}" for i in range(16)]
        self.app.grid_cameras = list(preset_ips)
        self.app.salvar_preset_atual("Nome Antigo")

        self.app._executar_renomear_preset("Nome Antigo", "Nome Novo")
        self.assertNotIn("Nome Antigo", self.app.presets_salvos)
        self.assertIn("Nome Novo", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Nome Novo"], preset_ips)
        self.assertEqual(self.app.preset_ativo, "Nome Novo")

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            persisted = json.load(f)
        self.assertNotIn("Nome Antigo", persisted)
        self.assertIn("Nome Novo", persisted)

    def test_delete_preset(self):
        self.app.grid_cameras = ["192.168.7.2"] * 16
        self.app.salvar_preset_atual("Preset Provisorio")
        self.assertIn("Preset Provisorio", self.app.presets_salvos)

        self.app.excluir_preset("Preset Provisorio")
        self.assertNotIn("Preset Provisorio", self.app.presets_salvos)
        self.assertIsNone(self.app.preset_ativo)

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            persisted = json.load(f)
        self.assertNotIn("Preset Provisorio", persisted)

    def test_preset_ui_elements(self):
        self.app.grid_cameras = ["192.168.7.10"] * 16
        self.app.salvar_preset_atual("Preset UI Test")
        self.app.mudar_aba_sidebar("Predefinições")

        self.assertGreaterEqual(len(self.app.preset_labels_referencia), 1)
        lbl = self.app.preset_labels_referencia[0]
        self.assertEqual(lbl.cget("text"), "Preset UI Test")

        # Simulate sidebar resize
        class MockEvent:
            x_root = 350
        self.app.ao_arrastar_divisor(MockEvent())
        self.assertGreater(lbl.cget("wraplength"), 0)

if __name__ == "__main__":
    unittest.main()
