import unittest
import os
import json
import tempfile
import shutil
import customtkinter as ctk
import Cameras

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.app = Cameras.CentralMonitoramento()
        self.app.withdraw()

        # Apontar arquivos temporários para isolamento dos testes
        self.app.arquivo_presets = os.path.join(self.test_dir, "presets_test.json")
        self.app.arquivo_grid = os.path.join(self.test_dir, "grid_test.json")
        self.app.presets_salvos = {}

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception:
            pass
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_salvar_multiplas_predefinicoes(self):
        """Testa o salvamento de múltiplas predefinições no arquivo JSON."""
        # Configura Grid 1
        self.app.grid_cameras = [f"192.168.7.{i+10}" for i in range(16)]
        self.app.salvar_preset_atual("Portaria")

        self.assertIn("Portaria", self.app.presets_salvos)
        self.assertEqual(len(self.app.presets_salvos["Portaria"]), 16)
        self.assertEqual(self.app.presets_salvos["Portaria"][0], "192.168.7.10")

        # Configura Grid 2
        self.app.grid_cameras = [f"192.168.7.{i+50}" for i in range(16)]
        self.app.salvar_preset_atual("Estacionamento")

        self.assertIn("Estacionamento", self.app.presets_salvos)
        self.assertEqual(len(self.app.presets_salvos), 2)

        # Configura Grid 3
        self.app.grid_cameras = [f"192.168.7.{i+100}" for i in range(16)]
        self.app.salvar_preset_atual("Galpao")

        self.assertIn("Galpao", self.app.presets_salvos)
        self.assertEqual(len(self.app.presets_salvos), 3)

        # Verifica persistência no arquivo JSON
        self.assertTrue(os.path.exists(self.app.arquivo_presets))
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertIn("Portaria", dados)
        self.assertIn("Estacionamento", dados)
        self.assertIn("Galpao", dados)

    def test_renomear_predefinicao(self):
        """Testa a renomeação de uma predefinição existente."""
        self.app.grid_cameras = ["192.168.7.20"] * 16
        self.app.salvar_preset_atual("Original")

        self.assertIn("Original", self.app.presets_salvos)

        self.app.confirmar_renomear_preset("Original", "Renomeado")
        self.assertNotIn("Original", self.app.presets_salvos)
        self.assertIn("Renomeado", self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos["Renomeado"], ["192.168.7.20"] * 16)

        # Testa com espaços em branco ao redor
        self.app.confirmar_renomear_preset("Renomeado", "  Novo Nome  ")
        self.assertIn("Novo Nome", self.app.presets_salvos)
        self.assertNotIn("Renomeado", self.app.presets_salvos)

    def test_deletar_predefinicao(self):
        """Testa a exclusão de uma predefinição."""
        self.app.grid_cameras = ["192.168.7.30"] * 16
        self.app.salvar_preset_atual("ParaDeletar")
        self.app.salvar_preset_atual("ParaManter")

        self.assertIn("ParaDeletar", self.app.presets_salvos)
        self.assertIn("ParaManter", self.app.presets_salvos)

        self.app.excluir_preset("ParaDeletar")
        self.assertNotIn("ParaDeletar", self.app.presets_salvos)
        self.assertIn("ParaManter", self.app.presets_salvos)

        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            dados = json.load(f)
        self.assertNotIn("ParaDeletar", dados)
        self.assertIn("ParaManter", dados)

    def test_aplicar_predefinicao_carrega_todas_cameras(self):
        """Testa que ao clicar/aplicar uma predefinição, todas as câmeras salvas são carregadas no grid."""
        cameras_preset1 = [f"192.168.7.{i+2}" for i in range(16)]
        self.app.presets_salvos["PresetCompleto"] = list(cameras_preset1)

        # Limpa o grid atual para 0.0.0.0
        self.app.grid_cameras = ["0.0.0.0"] * 16

        # Aplica a predefinição
        self.app.aplicar_preset("PresetCompleto")

        # Verifica se todas as câmeras foram carregadas nos 16 slots
        self.assertEqual(self.app.grid_cameras, cameras_preset1)

        # Verifica se o arquivo grid foi persistido
        with open(self.app.arquivo_grid, "r", encoding="utf-8") as f:
            grid_salvo = json.load(f)
        self.assertEqual(grid_salvo, cameras_preset1)

    def test_ui_predefinicoes_elementos(self):
        """Testa se a interface de predefinições cria os elementos visuais corretos e suporta redimensionamento."""
        self.app.presets_salvos["P1"] = ["192.168.7.2"] * 16
        self.app.presets_salvos["P2"] = ["192.168.7.3"] * 16

        self.app.mudar_aba_sidebar("Predefinições")
        self.assertEqual(self.app.aba_ativa, "Predefinições")
        self.assertEqual(len(self.app.preset_labels_referencia), 2)

        # Testa resize de sidebar ajustando wraplength
        class EventMock:
            def __init__(self, x_root):
                self.x_root = x_root

        mock_event = EventMock(x_root=self.app.winfo_rootx() + 350)
        self.app.ao_arrastar_divisor(mock_event)
        self.assertEqual(self.app.sidebar.cget("width"), 350)

        for lbl in self.app.preset_labels_referencia:
            self.assertEqual(lbl.cget("wraplength"), 350 - 110)

if __name__ == "__main__":
    unittest.main()
