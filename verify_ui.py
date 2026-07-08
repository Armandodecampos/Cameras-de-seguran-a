import os
import time
import threading
from Cameras import CentralMonitoramento
import mss

def interact():
    time.sleep(5)
    with mss.mss() as sct:
        sct.shot(output="final_ui_verification.png")
    print("Screenshot taken")
    os._exit(0)

if __name__ == "__main__":
    app = CentralMonitoramento()
    threading.Thread(target=interact, daemon=True).start()
    app.mainloop()
