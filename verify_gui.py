import os
import time
import mss
import threading
import customtkinter as ctk
from Cameras import CentralMonitoramento

def run_app():
    try:
        app = CentralMonitoramento()
        # Seleciona a aba de predefinições para o screenshot
        app.tabview.set("Predefinições")
        # Cria uma predefinição de teste para aparecer na lista
        app.predefinicoes["Teste UI"] = ["0.0.0.0"] * 20
        app.atualizar_lista_predefinicoes_ui()
        app.mainloop()
    except Exception as e:
        print(f"Erro ao rodar app: {e}")

# Start app in a thread
t = threading.Thread(target=run_app, daemon=True)
t.start()

# Wait for app to initialize and render
time.sleep(10)

# Take screenshot of the whole screen
with mss.mss() as sct:
    sct.shot(output="/home/jules/verification/gui_screenshot.png")

print("Screenshot capturado em /home/jules/verification/gui_screenshot.png")
