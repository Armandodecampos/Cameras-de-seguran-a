import unittest
import os
import json
from Cameras import CentralMonitoramento

class TestCameraPresets(unittest.TestCase):
    def setUp(self):
        self.app = CentralMonitoramento()

    def tearDown(self):
        self.app.destroy()
        if os.path.exists(self.app.arquivo_presets):
            try:
                os.remove(self.app.arquivo_presets)
            except Exception:
                pass

    def test_preset_lifecycle(self):
        # 1. Salvar primeira predefinição
        self.app.grid_cameras = ['192.168.7.2', '192.168.7.3'] + ['0.0.0.0'] * 14
        self.app._executar_salvamento_preset('Entrada e Saida')
        self.assertIn('Entrada e Saida', self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos['Entrada e Saida'][:2], ['192.168.7.2', '192.168.7.3'])

        # 2. Salvar segunda predefinição
        self.app.grid_cameras = ['192.168.7.10', '192.168.7.11', '192.168.7.12'] + ['0.0.0.0'] * 13
        self.app._executar_salvamento_preset('Estacionamento')
        self.assertIn('Estacionamento', self.app.presets_salvos)

        # 3. Carregar / Aplicar primeira predefinição
        self.app.aplicar_preset('Entrada e Saida')
        self.assertEqual(self.app.grid_cameras[0], '192.168.7.2')
        self.assertEqual(self.app.grid_cameras[1], '192.168.7.3')
        self.assertEqual(self.app.grid_cameras[2], '0.0.0.0')

        # 4. Renomear predefinição
        self.app._executar_renomear_preset('Entrada e Saida', 'Acesso Principal')
        self.assertNotIn('Entrada e Saida', self.app.presets_salvos)
        self.assertIn('Acesso Principal', self.app.presets_salvos)

        # 5. Carregar predefinição renomeada
        self.app.aplicar_preset('Acesso Principal')
        self.assertEqual(self.app.grid_cameras[0], '192.168.7.2')

        # 6. Deletar predefinição
        self.app.excluir_preset('Estacionamento')
        self.assertNotIn('Estacionamento', self.app.presets_salvos)
        self.assertIn('Acesso Principal', self.app.presets_salvos)

if __name__ == '__main__':
    unittest.main()
