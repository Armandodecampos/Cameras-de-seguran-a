import unittest
import os
import json
import Cameras

class TestPresets(unittest.TestCase):
    def setUp(self):
        self.app = Cameras.CentralMonitoramento()

    def tearDown(self):
        self.app.destroy()

    def test_salvar_preset(self):
        self.app.grid_cameras = ['192.168.7.2', '192.168.7.3'] + ['0.0.0.0'] * 14
        self.app._executar_salvamento_preset('Preset Entrada')
        self.assertIn('Preset Entrada', self.app.presets_salvos)
        self.assertEqual(self.app.presets_salvos['Preset Entrada'][:2], ['192.168.7.2', '192.168.7.3'])

    def test_aplicar_preset(self):
        self.app.presets_salvos['Preset Salvo'] = ['192.168.7.10', '192.168.7.11'] + ['0.0.0.0'] * 14
        self.app.grid_cameras = ['0.0.0.0'] * 16
        self.app.aplicar_preset('Preset Salvo')
        self.assertEqual(self.app.grid_cameras[:2], ['192.168.7.10', '192.168.7.11'])

    def test_renomear_preset(self):
        self.app._executar_salvamento_preset('Antigo')
        self.app._executar_renomear_preset('Antigo', 'Novo')
        self.assertNotIn('Antigo', self.app.presets_salvos)
        self.assertIn('Novo', self.app.presets_salvos)

    def test_excluir_preset(self):
        self.app._executar_salvamento_preset('Para Deletar')
        self.app.excluir_preset('Para Deletar')
        self.assertNotIn('Para Deletar', self.app.presets_salvos)

if __name__ == '__main__':
    unittest.main()
