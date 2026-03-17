import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Define a fake ctk module
class FakeCTk:
    class CTk:
        def __init__(self, *args, **kwargs): pass
        def title(self, *args, **kwargs): pass
        def geometry(self, *args, **kwargs): pass
        def protocol(self, *args, **kwargs): pass
        def bind(self, *args, **kwargs): pass
        def grid_columnconfigure(self, *args, **kwargs): pass
        def grid_rowconfigure(self, *args, **kwargs): pass
        def after(self, *args, **kwargs): pass
        def update_idletasks(self, *args, **kwargs): pass
        def state(self, *args, **kwargs): pass
        def winfo_x(self): return 0
        def winfo_y(self): return 0
        def winfo_width(self): return 1000
        def winfo_height(self): return 800

    def set_appearance_mode(self, mode): pass
    def CTkFrame(self, *args, **kwargs):
        m = MagicMock()
        m.winfo_children.return_value = []
        return m
    def CTkTabview(self, *args, **kwargs):
        m = MagicMock()
        m.tab.return_value = MagicMock()
        return m
    def CTkEntry(self, *args, **kwargs): return MagicMock()
    def CTkScrollableFrame(self, *args, **kwargs):
        m = MagicMock()
        m.winfo_children.return_value = []
        return m
    def CTkLabel(self, *args, **kwargs): return MagicMock()
    def CTkButton(self, *args, **kwargs): return MagicMock()
    def CTkImage(self, *args, **kwargs): return MagicMock()
    def CTkToplevel(self, *args, **kwargs): return MagicMock()

sys.modules["customtkinter"] = FakeCTk()
sys.modules["cv2"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["PIL.ImageTk"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["requests.auth"] = MagicMock()

import Cameras

class TestPredefinicoesLogic(unittest.TestCase):
    def setUp(self):
        with patch("threading.Thread"), \
             patch("os.path.expanduser", return_value="/tmp"), \
             patch("os.path.exists", return_value=False):
            self.app = Cameras.CentralMonitoramento()

        # Reset state for clean testing
        self.app.predefinicoes = {}
        self.app.grid_cameras = ["0.0.0.0"] * 20
        self.app.ultima_predefinicao = None
        self.app.camera_handlers = {}
        self.app.slot_labels = [MagicMock() for _ in range(20)]
        self.app.slot_ctk_images = [None] * 20
        self.app.img_vazia = MagicMock()

    def test_save_predefinicao(self):
        self.app.grid_cameras[0] = "192.168.1.10"
        with patch.object(self.app, "salvar_predefinicoes"), \
             patch.object(self.app, "atualizar_lista_predefinicoes_ui"):
            self.app._salvar_predefinicao("Teste1")

        self.assertIn("Teste1", self.app.predefinicoes)
        self.assertEqual(self.app.predefinicoes["Teste1"][0], "192.168.1.10")
        self.assertEqual(self.app.ultima_predefinicao, "Teste1")

    def test_apply_predefinicao(self):
        self.app.predefinicoes["Cenario1"] = ["10.0.0.1"] + (["0.0.0.0"] * 19)

        with patch.object(self.app, "iniciar_conexao_assincrona"), \
             patch.object(self.app, "pintar_predefinicao"), \
             patch.object(self.app, "salvar_grid"), \
             patch.object(self.app, "selecionar_slot"):
            self.app.aplicar_predefinicao("Cenario1")

        self.assertEqual(self.app.grid_cameras[0], "10.0.0.1")
        self.assertEqual(self.app.ultima_predefinicao, "Cenario1")

    def test_optimization_atribuir_ip(self):
        self.app.grid_cameras[0] = "192.168.1.50"

        with patch.object(self.app, "salvar_grid") as mock_save:
            # Should NOT call update if IP is the same and not forced
            self.app.atribuir_ip_ao_slot(0, "192.168.1.50", forcado=False)
            mock_save.assert_not_called()

            # Should call update if forced even if IP is the same
            self.app.atribuir_ip_ao_slot(0, "192.168.1.50", forcado=True)
            mock_save.assert_called()

    def test_reset_predefinicao_on_manual_change(self):
        self.app.ultima_predefinicao = "PresetAtivo"
        self.app.grid_cameras[0] = "1.1.1.1"

        with patch.object(self.app, "pintar_predefinicao") as mock_pintar, \
             patch.object(self.app, "iniciar_conexao_assincrona"):
            # Manual change (gerenciar_conexoes=True) should reset predefinicao
            self.app.atribuir_ip_ao_slot(0, "2.2.2.2", gerenciar_conexoes=True)
            self.assertIsNone(self.app.ultima_predefinicao)
            mock_pintar.assert_called_with("PresetAtivo", self.app.BG_SIDEBAR)

if __name__ == "__main__":
    unittest.main()
