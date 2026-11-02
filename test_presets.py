import os
import json
import tempfile
import shutil
import unittest
import customtkinter as ctk
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.app = CentralMonitoramento()
        self.app.arquivo_presets = os.path.join(self.temp_dir, "presets_config_test.json")
        self.app.arquivo_grid = os.path.join(self.temp_dir, "grid_config_test.json")
        self.app.presets_salvos = {}

    def tearDown(self):
        try:
            self.app.destroy()
        except:
            pass
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_salvar_e_carregar_preset(self):
        # Configura grid com IPs conhecidos
        test_ips = [f"192.168.7.{i+10}" for i in range(self.app.MAX_SLOTS)]
        self.app.grid_cameras = list(test_ips)

        # Salva o preset
        self.app._executar_salvamento_preset("Área Externa")

        # Verifica se o preset foi gravado no dicionário em memória
        self.assertIn("Área Externa", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Área Externa"], test_ips)

        # Verifica se foi persistido no arquivo JSON
        self.assertTrue(os.path.exists(self.app.arquivo_presets))
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertIn("Área Externa", dados)
        self.assertEqual(dados["Área Externa"], test_ips)

        # Testa recarregamento do arquivo
        recarregados = self.app.carregar_presets()
        self.assertIn("Área Externa", recarregados)
        self.assertEqual(recarregados["Área Externa"], test_ips)

    def test_renomear_preset(self):
        self.app.grid_cameras = [f"192.168.7.{i}" for i in range(self.app.MAX_SLOTS)]
        self.app._executar_salvamento_preset("Preset Antigo")

        # Renomeia
        self.app._executar_renomear_preset("Preset Antigo", "Preset Novo")

        self.assertNotIn("Preset Antigo", self.app.presets_salvos)
        self.assertIn("Preset Novo", self.app.presets_salvos)

        # Verifica arquivo JSON
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertNotIn("Preset Antigo", dados)
        self.assertIn("Preset Novo", dados)

    def test_excluir_preset(self):
        self.app._executar_salvamento_preset("Preset Para Deletar")
        self.assertIn("Preset Para Deletar", self.app.presets_salvos)

        # Exclui
        self.app.excluir_preset("Preset Para Deletar")
        self.assertNotIn("Preset Para Deletar", self.app.presets_salvos)

        # Verifica arquivo JSON
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertNotIn("Preset Para Deletar", dados)

    def test_aplicar_preset(self):
        # Cria e salva 2 presets diferentes
        preset_1_ips = [f"192.168.7.{100+i}" for i in range(self.app.MAX_SLOTS)]
        preset_2_ips = [f"192.168.7.{200+i}" for i in range(self.app.MAX_SLOTS)]

        self.app.presets_salvos["Preset 1"] = list(preset_1_ips)
        self.app.presets_salvos["Preset 2"] = list(preset_2_ips)

        # Inicia grid vazio
        self.app.grid_cameras = ["0.0.0.0"] * self.app.MAX_SLOTS

        # Aplica Preset 1
        self.app.aplicar_preset("Preset 1")
        self.assertEqual(self.app.grid_cameras, preset_1_ips)

        # Aplica Preset 2
        self.app.aplicar_preset("Preset 2")
        self.assertEqual(self.app.grid_cameras, preset_2_ips)

    def test_atualizar_lista_presets_ui_e_referencias(self):
        # Testa construção da UI de presets e armazenamento de referências para resize
        self.app.presets_salvos["Entrada Principal"] = ["192.168.7.2"] * self.app.MAX_SLOTS
        self.app.presets_salvos["Estacionamento"] = ["192.168.7.3"] * self.app.MAX_SLOTS

        self.app.mudar_aba_sidebar("Predefinições")
        self.app.atualizar_lista_presets_ui()

        # Deve haver 2 labels registrados em preset_labels_referencia
        self.assertEqual(len(self.app.preset_labels_referencia), 2)
        textos = [lbl.cget("text") for lbl in self.app.preset_labels_referencia]
        self.assertIn("Entrada Principal", textos)
        self.assertIn("Estacionamento", textos)


if __name__ == "__main__":
    unittest.main()
