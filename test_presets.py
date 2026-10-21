import unittest
import os
import json
import tempfile
import shutil
import customtkinter as ctk
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test configuration files
        self.test_dir = tempfile.mkdtemp()

        # Monkeypatch home directory / file paths in CentralMonitoramento
        self.orig_carregar_posicao = CentralMonitoramento.carregar_posicao_janela
        CentralMonitoramento.carregar_posicao_janela = lambda self: None

        # Instantiate app with headless mode / virtual display assumed
        self.app = CentralMonitoramento()
        self.app.withdraw()  # Hide main window during tests

        # Redirect file paths to test directory
        self.app.arquivo_presets = os.path.join(self.test_dir, "presets_config_abi.json")
        self.app.arquivo_grid = os.path.join(self.test_dir, "grid_config_abi.json")
        self.app.arquivo_config = os.path.join(self.test_dir, "config_cameras_abi.json")
        self.app.arquivo_ips = os.path.join(self.test_dir, "lista_ips_abi.json")

        # Re-initialize presets dictionary in app
        self.app.presets_salvos = {}
        self.app.salvar_presets()

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)
        CentralMonitoramento.carregar_posicao_janela = self.orig_carregar_posicao

    def test_salvar_preset(self):
        # Setup custom grid
        sample_grid = ["192.168.7.10", "192.168.7.11", "192.168.7.12", "0.0.0.0"] + ["0.0.0.0"] * 12
        self.app.grid_cameras = list(sample_grid)

        # Save preset
        preset_name = "Predefinição Entrada"
        self.app._executar_salvamento_preset(preset_name)

        # Assert in memory dict
        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name], sample_grid)

        # Assert JSON persistence
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn(preset_name, data)
        self.assertEqual(data[preset_name], sample_grid)

    def test_salvar_multiplas_predefinicoes(self):
        grid1 = ["192.168.7.2", "192.168.7.3"] + ["0.0.0.0"] * 14
        grid2 = ["192.168.7.20", "192.168.7.21", "192.168.7.22"] + ["0.0.0.0"] * 13

        self.app.grid_cameras = list(grid1)
        self.app._executar_salvamento_preset("Preset Bloco A")

        self.app.grid_cameras = list(grid2)
        self.app._executar_salvamento_preset("Preset Bloco B")

        self.assertEqual(len(self.app.presets_salvos), 2)
        self.assertEqual(self.app.presets_salvos["Preset Bloco A"], grid1)
        self.assertEqual(self.app.presets_salvos["Preset Bloco B"], grid2)

    def test_aplicar_preset(self):
        # Save two presets
        preset_a = ["192.168.7.5", "192.168.7.6"] + ["0.0.0.0"] * 14
        preset_b = ["192.168.7.50", "192.168.7.51", "192.168.7.52"] + ["0.0.0.0"] * 13

        self.app.presets_salvos["Zona Norte"] = list(preset_a)
        self.app.presets_salvos["Zona Sul"] = list(preset_b)
        self.app.salvar_presets()

        # Apply Zona Norte
        self.app.aplicar_preset("Zona Norte")
        self.assertEqual(self.app.grid_cameras, preset_a)

        # Apply Zona Sul
        self.app.aplicar_preset("Zona Sul")
        self.assertEqual(self.app.grid_cameras, preset_b)

    def test_renomear_preset(self):
        preset_data = ["192.168.7.100"] + ["0.0.0.0"] * 15
        old_name = "Antigo Nome"
        new_name = "Novo Nome"

        self.app.presets_salvos[old_name] = list(preset_data)
        self.app.salvar_presets()

        self.app._executar_renomear_preset(old_name, new_name)

        self.assertNotIn(old_name, self.app.presets_salvos)
        self.assertIn(new_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[new_name], preset_data)

        # Verify persistence
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn(old_name, data)
        self.assertIn(new_name, data)

    def test_excluir_preset(self):
        preset_name = "Para Excluir"
        self.app.presets_salvos[preset_name] = ["192.168.7.10"] + ["0.0.0.0"] * 15
        self.app.salvar_presets()

        self.app.excluir_preset(preset_name)

        self.assertNotIn(preset_name, self.app.presets_salvos)

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertNotIn(preset_name, data)

    def test_atualizar_lista_presets_ui(self):
        self.app.presets_salvos = {
            "P1": ["192.168.7.1"] + ["0.0.0.0"] * 15,
            "P2": ["192.168.7.2"] + ["0.0.0.0"] * 15
        }
        self.app.atualizar_lista_presets_ui()

        # Children of frame_presets should contain button and scroll frame
        children = self.app.frame_presets.winfo_children()
        self.assertGreaterEqual(len(children), 2)

if __name__ == "__main__":
    unittest.main()
