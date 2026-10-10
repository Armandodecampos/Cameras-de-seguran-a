import unittest
import os
import json
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.app = CentralMonitoramento()

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass

    def test_salvar_e_aplicar_preset(self):
        # Configura um grid customizado com 16 slots
        test_grid = [f"192.168.7.{i+2}" for i in range(16)]
        self.app.grid_cameras = list(test_grid)

        # Salva o preset "Preset Teste 1"
        self.app._executar_salvamento_preset("Preset Teste 1")
        self.assertIn("Preset Teste 1", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Preset Teste 1"], test_grid)

        # Limpa o grid atual
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # Aplica o preset
        self.app.aplicar_preset("Preset Teste 1")
        self.assertEqual(self.app.grid_cameras, test_grid)

    def test_renomear_preset(self):
        test_grid = ["192.168.7.10"] + ["0.0.0.0"] * 15
        self.app.grid_cameras = list(test_grid)
        self.app._executar_salvamento_preset("Antigo")

        self.app._executar_renomear_preset("Antigo", "Novo")
        self.assertNotIn("Antigo", self.app.presets_salvos)
        self.assertIn("Novo", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Novo"], test_grid)

    def test_excluir_preset(self):
        self.app._executar_salvamento_preset("ParaDeletar")
        self.assertIn("ParaDeletar", self.app.presets_salvos)

        self.app.excluir_preset("ParaDeletar")
        self.assertNotIn("ParaDeletar", self.app.presets_salvos)

    def test_persistencia_presets(self):
        nome_preset = "PresetPersistente"
        test_grid = ["192.168.7.50"] * 16
        self.app.grid_cameras = list(test_grid)
        self.app._executar_salvamento_preset(nome_preset)

        # Verifica se o arquivo foi salvo no disco
        self.assertTrue(os.path.exists(self.app.arquivo_presets))
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertIn(nome_preset, dados)
        self.assertEqual(dados[nome_preset], test_grid)

        # Limpa e exclui o preset
        self.app.excluir_preset(nome_preset)

if __name__ == "__main__":
    unittest.main()
