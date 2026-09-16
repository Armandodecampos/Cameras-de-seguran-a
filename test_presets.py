import os
import unittest
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.app = CentralMonitoramento()
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()

    def test_preset_lifecycle(self):
        # Set up a specific grid state
        test_ips = ["192.168.7.10", "192.168.7.11", "192.168.7.12"] + ["0.0.0.0"] * 13
        for i, ip in enumerate(test_ips):
            self.app.grid_cameras[i] = ip

        # 1. Save preset
        preset_name = "Test Preset Set 1"
        self.app._executar_salvamento_preset(preset_name)
        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name][:3], ["192.168.7.10", "192.168.7.11", "192.168.7.12"])

        # 2. Clear grid and apply preset
        self.app.grid_cameras = ["0.0.0.0"] * 16
        self.app.aplicar_preset(preset_name)
        self.assertEqual(self.app.grid_cameras[:3], ["192.168.7.10", "192.168.7.11", "192.168.7.12"])

        # 3. Rename preset
        new_preset_name = "Test Preset Set Renamed"
        self.app._executar_renomear_preset(preset_name, new_preset_name)
        self.assertNotIn(preset_name, self.app.presets_salvos)
        self.assertIn(new_preset_name, self.app.presets_salvos)

        # 4. Delete preset
        self.app.excluir_preset(new_preset_name)
        self.assertNotIn(new_preset_name, self.app.presets_salvos)

if __name__ == "__main__":
    unittest.main()
