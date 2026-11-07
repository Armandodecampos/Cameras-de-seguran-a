import unittest
import os
import json
import shutil
import tempfile
from unittest.mock import patch, MagicMock

# Set headless / mock setup before importing GUI
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

from Cameras import CentralMonitoramento

class TestPresetsManagement(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_expanduser = os.path.expanduser
        os.path.expanduser = lambda path: self.test_dir if path == "~" else self.orig_expanduser(path)

        # Create dummy preset file
        self.presets_file = os.path.join(self.test_dir, "presets_config_abi.json")
        self.grid_file = os.path.join(self.test_dir, "grid_config_abi.json")

        self.initial_presets = {
            "Preset Teste 1": ["192.168.7.2", "192.168.7.3"] + ["0.0.0.0"] * 14,
            "Preset Teste 2": ["192.168.7.20", "192.168.7.21"] + ["0.0.0.0"] * 14
        }
        with open(self.presets_file, "w", encoding="utf-8") as f:
            json.dump(self.initial_presets, f)

        # Mock threaded connection loops
        with patch.object(CentralMonitoramento, "iniciar_conexao_assincrona", return_value=None), \
             patch.object(CentralMonitoramento, "alternar_todos_streams", return_value=None), \
             patch.object(CentralMonitoramento, "loop_exibicao", return_value=None):
            self.app = CentralMonitoramento()

    def tearDown(self):
        try:
            self.app.destroy()
        except:
            pass
        os.path.expanduser = self.orig_expanduser
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_carregar_presets(self):
        presets = self.app.carregar_presets()
        self.assertIn("Preset Teste 1", presets)
        self.assertIn("Preset Teste 2", presets)
        self.assertEqual(len(presets), 2)

    def test_salvar_preset_atual(self):
        # Set a customized grid
        custom_grid = [f"192.168.7.{100 + i}" for i in range(16)]
        self.app.grid_cameras = list(custom_grid)

        # Save as new preset
        self.app._executar_salvamento_preset("Preset Novo")

        self.assertIn("Preset Novo", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset Novo"], custom_grid)

        # Check persistence
        with open(self.presets_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertIn("Preset Novo", saved_data)
        self.assertEqual(saved_data["Preset Novo"], custom_grid)

    def test_aplicar_preset(self):
        # Initial grid is default
        self.app.grid_cameras = ["0.0.0.0"] * 16

        with patch.object(self.app, "iniciar_conexao_assincrona", return_value=None):
            self.app.aplicar_preset("Preset Teste 1")

        self.assertEqual(self.app.grid_cameras[0], "192.168.7.2")
        self.assertEqual(self.app.grid_cameras[1], "192.168.7.3")
        self.assertEqual(self.app.grid_cameras[2], "0.0.0.0")

        # Verify grid config was saved
        with open(self.grid_file, "r", encoding="utf-8") as f:
            grid_saved = json.load(f)
        self.assertEqual(grid_saved[0], "192.168.7.2")
        self.assertEqual(grid_saved[1], "192.168.7.3")

    def test_renomear_preset(self):
        self.app._executar_renomear_preset("Preset Teste 1", "Preset Renomeado")

        self.assertNotIn("Preset Teste 1", self.app.presets_salvos)
        self.assertIn("Preset Renomeado", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset Renomeado"][0], "192.168.7.2")

        # Check persistence
        with open(self.presets_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertNotIn("Preset Teste 1", saved_data)
        self.assertIn("Preset Renomeado", saved_data)

    def test_excluir_preset(self):
        self.app.excluir_preset("Preset Teste 2")

        self.assertNotIn("Preset Teste 2", self.app.presets_salvos)

        # Check persistence
        with open(self.presets_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertNotIn("Preset Teste 2", saved_data)

    def test_atualizar_lista_presets_ui(self):
        self.app.mudar_aba_sidebar("Predefinições")
        self.assertEqual(len(self.app.preset_labels_referencia), len(self.app.presets_salvos))

        # Check drag resizing updates preset label wraplength without exception
        event = MagicMock()
        event.x_root = self.app.winfo_rootx() + 350
        self.app.ao_arrastar_divisor(event)

        for lbl in self.app.preset_labels_referencia:
            self.assertEqual(lbl.cget("wraplength"), max(50, 350 - 110))

if __name__ == "__main__":
    unittest.main()
