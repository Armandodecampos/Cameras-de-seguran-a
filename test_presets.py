import unittest
import os
import json
import customtkinter as ctk
import Cameras

class TestCameraPresets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ctk.set_appearance_mode("Dark")

    def setUp(self):
        self.app = Cameras.CentralMonitoramento()
        self.app.withdraw()  # Hide main window during test

    def tearDown(self):
        self.app.destroy()

    def test_salvar_e_carregar_preset(self):
        # Configure grid with test IPs
        test_ips = ["192.168.7.10", "192.168.7.20"] + ["0.0.0.0"] * 14
        self.app.grid_cameras = list(test_ips)

        # Save preset directly via helper
        preset_name = "Preset Teste 1"
        self.app._executar_salvamento_preset(preset_name)

        # Check in memory presets
        self.assertIn(preset_name, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[preset_name], test_ips)

        # Check JSON persistence
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertIn(preset_name, saved_data)
        self.assertEqual(saved_data[preset_name], test_ips)

    def test_aplicar_preset(self):
        preset_name = "Preset Layout Sala"
        test_ips = ["192.168.7.100", "192.168.7.101", "192.168.7.102"] + ["0.0.0.0"] * 13
        self.app.presets_salvos[preset_name] = test_ips

        # Apply preset
        self.app.aplicar_preset(preset_name)

        # Verify grid_cameras updated
        self.assertEqual(self.app.grid_cameras, test_ips)

    def test_renomear_preset(self):
        antigo_nome = "Antigo Preset"
        novo_nome = "Novo Preset Renomeado"
        test_ips = ["192.168.7.5"] + ["0.0.0.0"] * 15

        self.app.presets_salvos[antigo_nome] = test_ips
        self.app.salvar_presets()

        self.app._executar_renomear_preset(antigo_nome, novo_nome)

        self.assertNotIn(antigo_nome, self.app.presets_salvos)
        self.assertIn(novo_nome, self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos[novo_nome], test_ips)

        # Verify JSON
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertNotIn(antigo_nome, saved_data)
        self.assertIn(novo_nome, saved_data)

    def test_excluir_preset(self):
        preset_name = "Preset Para Deletar"
        self.app.presets_salvos[preset_name] = ["0.0.0.0"] * 16
        self.app.salvar_presets()

        self.app.excluir_preset(preset_name)

        self.assertNotIn(preset_name, self.app.presets_salvos)

        # Verify JSON
        with open(self.app.arquivo_presets, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        self.assertNotIn(preset_name, saved_data)

    def test_ui_preset_references(self):
        self.app.presets_salvos["Preset UI 1"] = ["0.0.0.0"] * 16
        self.app.presets_salvos["Preset UI 2"] = ["0.0.0.0"] * 16

        self.app.atualizar_lista_presets_ui()

        self.assertIn("Preset UI 1", self.app.preset_labels_referencia)
        self.assertIn("Preset UI 2", self.app.preset_labels_referencia)
        self.assertIsInstance(self.app.preset_labels_referencia["Preset UI 1"], ctk.CTkLabel)

if __name__ == "__main__":
    unittest.main()
