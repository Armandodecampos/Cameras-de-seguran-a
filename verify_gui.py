import customtkinter as ctk
import mss
import os
import threading
import time
from unittest.mock import MagicMock, patch

# Mock cv2.VideoCapture to avoid RTSP connection attempts
with patch('cv2.VideoCapture'), patch('requests.put'), patch('requests.get'):
    from Cameras import CentralMonitoramento

    def run_app():
        app = CentralMonitoramento()

        # Mock some predefinitions for display
        app.predefinicoes = {
            "Teste Sala": ["192.168.7.2"] * 20,
            "Teste Portaria": ["192.168.7.3"] * 20
        }
        app.ultima_predefinicao = "Teste Sala"

        # We need to manually trigger UI update since we are in a mock environment
        app.after(1000, app.atualizar_lista_predefinicoes_ui)
        app.after(1500, lambda: app.tabview.set("Predefinições"))

        # Close app after some time
        app.after(5000, app.destroy)
        app.mainloop()

    if __name__ == "__main__":
        # Ensure directories exist
        os.makedirs("/home/jules/verification/screenshots", exist_ok=True)

        # Start app in a thread
        t = threading.Thread(target=run_app)
        t.daemon = True
        t.start()

        # Wait for app to start
        time.sleep(3)

        # Take screenshot using mss
        with mss.mss() as sct:
            sct.shot(output="/home/jules/verification/screenshots/verification.png")

        print("Screenshot saved to /home/jules/verification/screenshots/verification.png")
        time.sleep(3) # Give time for app to close
