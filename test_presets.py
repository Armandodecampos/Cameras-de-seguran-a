import unittest
import os
import json
import tempfile
import Cameras

class TestPresets(unittest.TestCase):
    def setUp(self):
        self.app = Cameras.CentralMonitoramento()

    def tearDown(self):
        self.app.destroy()

    def test_preset_lifecycle(self):
        # 1. Clear or initialize presets
        self.app.presets_salvos = {}

        # 2. Set grid state 1 and save preset "Preset Alpha"
        grid_state_1 = ["192.168.7.2", "192.168.7.3", "192.168.7.4", "192.168.7.20"] + ["0.0.0.0"] * 12
        self.app.grid_cameras = list(grid_state_1)
        self.app._executar_salvamento_preset("Preset Alpha")

        self.assertIn("Preset Alpha", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset Alpha"], grid_state_1)

        # 3. Set grid state 2 and save preset "Preset Beta"
        grid_state_2 = ["192.168.7.21", "192.168.7.22", "192.168.7.23", "0.0.0.0"] + ["0.0.0.0"] * 12
        self.app.grid_cameras = list(grid_state_2)
        self.app._executar_salvamento_preset("Preset Beta")

        self.assertIn("Preset Beta", self.app.presets_salvos)
        self.assertEqual(len(self.app.presets_salvos), 2)

        # 4. Clear active grid
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # 5. Apply "Preset Alpha" and verify grid restoration
        self.app.aplicar_preset("Preset Alpha")
        self.assertEqual(self.app.grid_cameras, grid_state_1)

        # 6. Apply "Preset Beta" and verify grid restoration
        self.app.aplicar_preset("Preset Beta")
        self.assertEqual(self.app.grid_cameras, grid_state_2)

        # 7. Rename "Preset Alpha" to "Preset Alpha Renomeado"
        self.app._executar_renomear_preset("Preset Alpha", "Preset Alpha Renomeado")
        self.assertNotIn("Preset Alpha", self.app.presets_salvos)
        self.assertIn("Preset Alpha Renomeado", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset Alpha Renomeado"], grid_state_1)

        # 8. Delete "Preset Beta"
        self.app.excluir_preset("Preset Beta")
        self.assertNotIn("Preset Beta", self.app.presets_salvos)
        self.assertEqual(list(self.app.presets_salvos.keys()), ["Preset Alpha Renomeado"])

if __name__ == "__main__":
    unittest.main()
