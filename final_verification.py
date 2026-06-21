import customtkinter as ctk
from Cameras import CentralMonitoramento
import threading
import time
import os
from mss import mss

def take_screenshot(filename):
    with mss() as sct:
        sct.shot(output=filename)

def run_app():
    app = CentralMonitoramento()
    app.tab_var.set("Predefinições")
    app.mudar_aba_sidebar("Predefinições")

    # Adicionar alguns presets para demonstração
    app.presets_salvos["Entrada Principal"] = ["0.0.0.0"] * 16
    app.presets_salvos["Estacionamento"] = ["0.0.0.0"] * 16
    app.presets_salvos["Escritorio - Vista Geral"] = ["0.0.0.0"] * 16
    app.salvar_presets()
    app.atualizar_lista_presets_ui()

    def delayed_screenshot():
        time.sleep(3)
        os.makedirs("/home/jules/verification/screenshots", exist_ok=True)
        take_screenshot("/home/jules/verification/screenshots/final_presets_ui.png")
        app.quit()

    threading.Thread(target=delayed_screenshot, daemon=True).start()
    app.mainloop()

if __name__ == "__main__":
    run_app()
