import unittest
import os
import json
import shutil
import tempfile
import Cameras

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.arquivo_presets = os.path.join(self.test_dir, "presets_config_abi.json")
        self.arquivo_grid = os.path.join(self.test_dir, "grid_config_abi.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_preset_save_apply_rename_delete(self):
        app = Cameras.CentralMonitoramento()
        app.arquivo_presets = self.arquivo_presets
        app.arquivo_grid = self.arquivo_grid

        # 1. Configura a grade com algumas câmeras de teste
        test_ips = ["192.168.7.10", "192.168.7.11", "192.168.7.12", "192.168.7.13"]
        for i, ip in enumerate(test_ips):
            app.grid_cameras[i] = ip

        # 2. Salva predefinição
        preset_name = "Entrada Principal"
        app._executar_salvamento_preset(preset_name)

        self.assertIn(preset_name, app.presets_salvos)
        self.assertEqual(app.presets_salvos[preset_name][:4], test_ips)

        # Verifica se foi salvo no arquivo JSON
        with open(self.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn(preset_name, data)
            self.assertEqual(data[preset_name][:4], test_ips)

        # 3. Limpa a grade e aplica a predefinição
        for i in range(app.MAX_SLOTS):
            app.grid_cameras[i] = "0.0.0.0"

        app.aplicar_preset(preset_name)

        self.assertEqual(app.grid_cameras[:4], test_ips)
        for i in range(4, app.MAX_SLOTS):
            self.assertEqual(app.grid_cameras[i], "0.0.0.0")

        # 4. Renomeia a predefinição
        novo_nome = "Entrada Modificada"
        app._executar_renomear_preset(preset_name, novo_nome)

        self.assertNotIn(preset_name, app.presets_salvos)
        self.assertIn(novo_nome, app.presets_salvos)

        with open(self.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertNotIn(preset_name, data)
            self.assertIn(novo_nome, data)

        # 5. Exclui a predefinição
        app.excluir_preset(novo_nome)

        self.assertNotIn(novo_nome, app.presets_salvos)
        with open(self.arquivo_presets, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertNotIn(novo_nome, data)

        app.destroy()

if __name__ == "__main__":
    unittest.main()
