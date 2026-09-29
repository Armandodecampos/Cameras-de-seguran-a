import os
import json
import unittest
from unittest.mock import patch, MagicMock
import customtkinter as ctk

import Cameras

class TestPresetsManagement(unittest.TestCase):
    def setUp(self):
        # Patch tkinter mainloop/update methods to prevent blocking
        self.app = Cameras.CentralMonitoramento()
        self.app.withdraw() # Hide window during test

    def tearDown(self):
        try:
            self.app.destroy()
        except:
            pass

    def test_save_rename_delete_apply_presets(self):
        # 1. Setup sample grid
        sample_grid = ["192.168.7.10"] * 16
        self.app.grid_cameras = list(sample_grid)

        # 2. Test saving presets
        self.app._executar_salvamento_preset("Preset 1 - Guarita")
        self.assertIn("Preset 1 - Guarita", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset 1 - Guarita"], sample_grid)

        # Verify disk persistence
        self.assertTrue(os.path.exists(self.app.arquivo_presets))
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data_on_disk = json.load(f)
        self.assertIn("Preset 1 - Guarita", data_on_disk)
        self.assertEqual(data_on_disk["Preset 1 - Guarita"], sample_grid)

        # 3. Save second preset with different grid
        sample_grid_2 = ["192.168.7.20" if i % 2 == 0 else "0.0.0.0" for i in range(16)]
        self.app.grid_cameras = list(sample_grid_2)
        self.app._executar_salvamento_preset("Preset 2 - Estacionamento")
        self.assertIn("Preset 2 - Estacionamento", self.app.presets_salvos)

        # 4. Test applying preset 1
        self.app.aplicar_preset("Preset 1 - Guarita")
        self.assertEqual(self.app.grid_cameras, sample_grid)

        # 5. Test applying preset 2
        self.app.aplicar_preset("Preset 2 - Estacionamento")
        self.assertEqual(self.app.grid_cameras, sample_grid_2)

        # 6. Test renaming preset
        self.app._executar_renomear_preset("Preset 1 - Guarita", "Preset 1 - Portão Principal")
        self.assertNotIn("Preset 1 - Guarita", self.app.presets_salvos)
        self.assertIn("Preset 1 - Portão Principal", self.app.presets_salvos)

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data_on_disk = json.load(f)
        self.assertNotIn("Preset 1 - Guarita", data_on_disk)
        self.assertIn("Preset 1 - Portão Principal", data_on_disk)

        # 7. Test deleting preset
        self.app.excluir_preset("Preset 2 - Estacionamento")
        self.assertNotIn("Preset 2 - Estacionamento", self.app.presets_salvos)

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data_on_disk = json.load(f)
        self.assertNotIn("Preset 2 - Estacionamento", data_on_disk)

        # 8. Test UI references updated
        self.app.atualizar_lista_presets_ui()
        self.assertIn("Preset 1 - Portão Principal", self.app.preset_labels_referencia)

if __name__ == "__main__":
    unittest.main()
