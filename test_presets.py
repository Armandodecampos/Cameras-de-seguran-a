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

    def test_salvar_preset(self):
        self.app.grid_cameras[0] = "192.168.7.10"
        self.app.grid_cameras[1] = "192.168.7.20"

        self.app._executar_salvamento_preset("Preset Teste 1")

        self.assertIn("Preset Teste 1", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset Teste 1"][0], "192.168.7.10")
        self.assertEqual(self.app.presets_salvos["Preset Teste 1"][1], "192.168.7.20")

        # Verify JSON persistence
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
            self.assertIn("Preset Teste 1", dados)

    def test_aplicar_preset(self):
        # Save a preset
        ips_salvos = ["192.168.7.100", "192.168.7.101"] + ["0.0.0.0"] * (self.app.MAX_SLOTS - 2)
        self.app.presets_salvos["Preset Teste 2"] = ips_salvos
        self.app.salvar_presets()

        # Apply preset
        self.app.aplicar_preset("Preset Teste 2")

        self.assertEqual(self.app.grid_cameras[0], "192.168.7.100")
        self.assertEqual(self.app.grid_cameras[1], "192.168.7.101")
        self.assertEqual(self.app.grid_cameras[2], "0.0.0.0")

    def test_renomear_preset(self):
        self.app.presets_salvos["Antigo Nome"] = ["192.168.7.5"] + ["0.0.0.0"] * (self.app.MAX_SLOTS - 1)
        self.app.salvar_presets()

        self.app._executar_renomear_preset("Antigo Nome", "Novo Nome")

        self.assertNotIn("Antigo Nome", self.app.presets_salvos)
        self.assertIn("Novo Nome", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo Nome"][0], "192.168.7.5")

    def test_excluir_preset(self):
        self.app.presets_salvos["Para Deletar"] = ["0.0.0.0"] * self.app.MAX_SLOTS
        self.app.salvar_presets()

        self.app.excluir_preset("Para Deletar")

        self.assertNotIn("Para Deletar", self.app.presets_salvos)

    def test_ui_preset_labels_referencia(self):
        self.app.presets_salvos["Preset UI Teste"] = ["0.0.0.0"] * self.app.MAX_SLOTS
        self.app.atualizar_lista_presets_ui()

        self.assertIn("Preset UI Teste", self.app.preset_labels_referencia)
        lbl = self.app.preset_labels_referencia["Preset UI Teste"]
        self.assertEqual(lbl.cget("text"), "Preset UI Teste")

if __name__ == "__main__":
    unittest.main()
