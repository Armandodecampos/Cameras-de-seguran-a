import unittest
import os
import json
import tempfile
import shutil
from unittest.mock import patch
import customtkinter as ctk
from Cameras import CentralMonitoramento

class TestPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

        self.p_loop = patch.object(CentralMonitoramento, 'loop_exibicao', lambda self: None)
        self.p_proc = patch.object(CentralMonitoramento, '_processar_fila_conexoes_pendentes', lambda self: None)

        self.p_loop.start()
        self.p_proc.start()

        self.app = CentralMonitoramento()
        self.app.withdraw()

        # Redirect instance file locations to test_dir
        self.app.arquivo_presets = os.path.join(self.test_dir, "presets_config_abi.json")
        self.app.arquivo_grid = os.path.join(self.test_dir, "grid_config_abi.json")
        self.app.arquivo_config = os.path.join(self.test_dir, "config_cameras_abi.json")
        self.app.arquivo_janela = os.path.join(self.test_dir, "config_janela_abi.json")
        self.app.arquivo_ips = os.path.join(self.test_dir, "lista_ips_abi.json")
        self.app.diretorio_snapshots = os.path.join(self.test_dir, "snapshots_abi")
        os.makedirs(self.app.diretorio_snapshots, exist_ok=True)

        self.app.presets_salvos = {}

    def tearDown(self):
        try:
            self.app.destroy()
        except:
            pass
        patch.stopall()
        shutil.rmtree(self.test_dir)

    def test_salvar_e_carregar_preset(self):
        sample_grid = ["192.168.7.10"] + ["0.0.0.0"] * 15
        self.app.grid_cameras = list(sample_grid)

        preset_name = "Entrada Principal"
        self.app._executar_salvamento_preset(preset_name)

        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name], sample_grid)

        loaded_presets = self.app.carregar_presets()
        self.assertIn(preset_name, loaded_presets)
        self.assertEqual(loaded_presets[preset_name], sample_grid)

    def test_aplicar_preset(self):
        target_grid = [f"192.168.7.{i+1}" for i in range(16)]
        self.app.presets_salvos["Patrulha Noturna"] = target_grid

        self.app.grid_cameras = ["0.0.0.0"] * 16

        self.app.aplicar_preset("Patrulha Noturna")

        self.assertEqual(self.app.grid_cameras, target_grid)

    def test_renomear_preset(self):
        preset_ips = ["192.168.7.5"] + ["0.0.0.0"] * 15
        self.app.presets_salvos["Antigo Nome"] = preset_ips
        self.app.salvar_presets()

        self.app._executar_renomear_preset("Antigo Nome", "Novo Nome")

        self.assertNotIn("Antigo Nome", self.app.presets_salvos)
        self.assertIn("Novo Nome", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo Nome"], preset_ips)

        loaded = self.app.carregar_presets()
        self.assertNotIn("Antigo Nome", loaded)
        self.assertIn("Novo Nome", loaded)

    def test_excluir_preset(self):
        self.app.presets_salvos["Temp Preset"] = ["192.168.7.20"] * 16
        self.app.salvar_presets()

        self.app.excluir_preset("Temp Preset")

        self.assertNotIn("Temp Preset", self.app.presets_salvos)
        loaded = self.app.carregar_presets()
        self.assertNotIn("Temp Preset", loaded)

    def test_ui_preset_labels_referencia(self):
        self.app.presets_salvos["Preset 1"] = ["0.0.0.0"] * 16
        self.app.presets_salvos["Preset 2"] = ["0.0.0.0"] * 16

        self.app.atualizar_lista_presets_ui()

        self.assertEqual(len(self.app.preset_labels_referencia), 2)
        label_texts = [lbl.cget("text") for lbl in self.app.preset_labels_referencia]
        self.assertIn("Preset 1", label_texts)
        self.assertIn("Preset 2", label_texts)

if __name__ == "__main__":
    unittest.main()
