import os
import time
import mss
import threading
import customtkinter as ctk
from Cameras import CentralMonitoramento

def run_app():
    try:
        app = CentralMonitoramento()
        app.geometry("1200x800")
        app.update()

        # Seleciona a aba de predefinições
        app.tabview.set("Predefinições")

        # Cria predefinições de teste
        app.predefinicoes["A - Teste 1"] = ["0.0.0.0"] * 20
        app.predefinicoes["B - Teste 2"] = ["0.0.0.0"] * 20
        app.atualizar_lista_predefinicoes_ui()

        print(f"Predefinições no app: {list(app.predefinicoes.keys())}")
        print(f"Widgets na scroll_predefinicoes: {len(app.scroll_predefinicoes.winfo_children())}")

        app.mainloop()
    except Exception as e:
        print(f"Erro ao rodar app: {e}")

# Start app in a thread
t = threading.Thread(target=run_app, daemon=True)
t.start()

# Wait for app to initialize and render
time.sleep(15)

# Take screenshot of the whole screen
with mss.mss() as sct:
    sct.shot(output="/home/jules/verification/gui_screenshot_v2.png")

print("Screenshot capturado em /home/jules/verification/gui_screenshot_v2.png")
