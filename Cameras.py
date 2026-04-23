import cv2
import customtkinter as ctk
from PIL import Image, ImageTk
import json
import os
import threading
import time
import socket
import queue
import requests
from requests.auth import HTTPDigestAuth
# Configuração de baixa latência para OpenCV/FFMPEG
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp;stimeout;5000000;buffer_size;2048000;analyzeduration;100000;probesize;100000;fflags;discardcorrupt;max_delay;500000;reorder_queue_size;16;rtsp_flags;prefer_tcp;reconnect;1;reconnect_streamed;1;reconnect_at_eof;1"
cv2.setNumThreads(1)

# Semáforo global para limitar conexões simultâneas (evita travamentos)
sem_conexao = threading.Semaphore(4)

# --- CLASSE DE VÍDEO OTIMIZADA ---
class CameraHandler:
    def __init__(self, ip, canal=102, user="admin", password="password"):
        self.ip = ip
        self.canal = canal
        self.user = user
        self.password = password
        self.url = self._gerar_url(ip, canal)
        self.cap = None
        self.rodando = False
        self.frame_pil = None
        self.novo_frame = False
        self.lock = threading.Lock()
        self.conectado = False
        self.tamanho_alvo = (640, 480)
        self.interpolation = cv2.INTER_NEAREST
        self.ip_display = ip
        self.nome_display = ""
        self.exibir_info = False
        self.prioridade = False
        self.necessita_reconexao = False

    def _gerar_url(self, ip, canal):
        # RTSP String Padrão Hikvision/Intelbras
        import urllib.parse
        encoded_pass = urllib.parse.quote(self.password)
        return f"rtsp://{self.user}:{encoded_pass}@{ip}:554/Streaming/Channels/{canal}"

    def set_prioridade(self, estado):
        with self.lock:
            self.prioridade = estado

    def set_exibir_info(self, estado):
        with self.lock:
            self.exibir_info = estado

    def set_canal(self, novo_canal):
        with self.lock:
            if self.canal != novo_canal:
                self.canal = novo_canal
                self.url = self._gerar_url(self.ip, novo_canal)
                self.necessita_reconexao = True

    def iniciar(self):
        try:
            print(f"Tentando conectar em: {self.ip_display} (Canal {self.canal})...")

            # Usa o semáforo para não abrir muitas conexões ao mesmo tempo
            with sem_conexao:
                self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

            if hasattr(cv2, 'CAP_PROP_OPEN_TIMEOUT_USEC'):
                try: self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_USEC, 5000000)
                except: pass

            if hasattr(cv2, 'CAP_PROP_BUFFERSIZE'):
                try: self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
                except: pass

            if self.cap.isOpened():
                self.rodando = True
                self.conectado = True
                threading.Thread(target=self.loop_leitura, daemon=True).start()
                print(f"Conectado com sucesso: {self.ip_display}")
                return True
            else:
                print(f"Falha ao abrir stream: {self.ip_display}")
                return False
        except Exception as e:
            print(f"Erro driver ({self.ip_display}): {e}")
            return False

    def loop_leitura(self):
        consecutive_failures = 0
        last_process_time = 0

        while self.rodando:
            if self.necessita_reconexao:
                with self.lock:
                    print(f"Alterando canal de {self.ip_display} para {self.canal}...")
                    if self.cap: self.cap.release()
                    with sem_conexao:
                        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                    if hasattr(cv2, 'CAP_PROP_BUFFERSIZE'):
                        try: self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
                        except: pass
                    self.necessita_reconexao = False
                    consecutive_failures = 0

            if not self.cap or not self.cap.isOpened():
                time.sleep(0.5)
                continue

            # Grab frame (rápido, não decodifica)
            ret = self.cap.grab()

            if ret:
                consecutive_failures = 0
                now = time.time()

                # Controle de FPS Dinâmico (Reduzido para 5 em background para economizar CPU)
                target_fps = 25 if self.prioridade else 5
                if now - last_process_time < (1.0 / target_fps):
                    continue

                # Se a UI ainda não consumiu o frame anterior, e não é prioridade, podemos pular
                if self.novo_frame and not self.prioridade:
                    continue

                # Retrieve frame (decodifica)
                ret_ret, frame = self.cap.retrieve()
                if not ret_ret:
                    continue

                last_process_time = now

                try:
                    w, h = self.tamanho_alvo
                    w, h = int(w), int(h)

                    if frame.shape[1] != w or frame.shape[0] != h:
                        frame_res = cv2.resize(frame, (w, h), interpolation=self.interpolation)
                    else:
                        frame_res = frame

                    # Adiciona Nome e IP para debug visual apenas se houver espaço e estiver habilitado
                    if h > 50 and self.exibir_info:
                        # Nome da Câmera (Superior Esquerda)
                        if self.nome_display:
                            cv2.putText(frame_res, self.nome_display, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
                            cv2.putText(frame_res, self.nome_display, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

                        # IP da Câmera (Linha abaixo)
                        cv2.putText(frame_res, self.ip_display, (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
                        cv2.putText(frame_res, self.ip_display, (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

                    rgb = cv2.cvtColor(frame_res, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb)

                    with self.lock:
                        self.frame_pil = pil_img
                        self.novo_frame = True
                except Exception as e:
                    time.sleep(0.01)
            else:
                consecutive_failures += 1
                if consecutive_failures > 50: # Reduzido de 100 para 50 para reagir mais rápido
                    print(f"LOG: Camera {self.ip_display} sem frames. Tentando reconectar...")
                    if self.cap: self.cap.release()
                    with sem_conexao:
                        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                    consecutive_failures = 0

                # Sleep progressivo em caso de falha para evitar overhead de CPU
                sleep_time = min(0.2, 0.01 * consecutive_failures)
                time.sleep(sleep_time)

        if self.cap:
            self.cap.release()
        self.rodando = False
        self.conectado = False

    def pegar_frame(self):
        with self.lock:
            self.novo_frame = False
            return self.frame_pil

    def parar(self):
        self.rodando = False
        self.conectado = False

# --- INTERFACE PRINCIPAL ---
class CentralMonitoramento(ctk.CTk):
    def _get_window_scaling(self):
        try:
            return super()._get_window_scaling()
        except:
            return 1.0

    BG_MAIN = "#121212"
    BG_SIDEBAR = "#1A1A1A"
    BG_PANEL = "#1E1E1E"
    ACCENT_RED = "#D32F2F"
    ACCENT_WINE = "#7B1010"
    TEXT_P = "#E0E0E0"
    TEXT_S = "#9E9E9E"
    GRAY_DARK = "#424242"

    def __init__(self):
        super().__init__()

        self.title("Sistema de Monitoramento ABI - Full Control V5 + PTZ")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")

        # Credenciais para PTZ
        self.user_ptz = "admin"
        self.pass_ptz = "1357gov@"

        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)

        # Binds de Teclado
        self.bind("<Escape>", lambda event: self.sair_tela_cheia())

        # Binds para PTZ
        self.bind("<KeyPress-Up>", lambda e: self.comando_ptz("UP"))
        self.bind("<KeyPress-Down>", lambda e: self.comando_ptz("DOWN"))
        self.bind("<KeyPress-Left>", lambda e: self.comando_ptz("LEFT"))
        self.bind("<KeyPress-Right>", lambda e: self.comando_ptz("RIGHT"))

        self.bind("<KeyRelease-Up>", lambda e: self.comando_ptz("STOP"))
        self.bind("<KeyRelease-Down>", lambda e: self.comando_ptz("STOP"))
        self.bind("<KeyRelease-Left>", lambda e: self.comando_ptz("STOP"))
        self.bind("<KeyRelease-Right>", lambda e: self.comando_ptz("STOP"))

        # Configurações de Arquivos
        user_dir = os.path.expanduser("~")
        self.arquivo_config = os.path.join(user_dir, "config_cameras_abi.json")
        self.arquivo_grid = os.path.join(user_dir, "grid_config_abi.json")
        self.arquivo_janela = os.path.join(user_dir, "config_janela_abi.json")
        self.arquivo_predefinicoes = os.path.join(user_dir, "predefinicoes_grid_abi.json")
        self.arquivo_ips = os.path.join(user_dir, "lista_ips_abi.json")

        self.botoes_referencia = {}
        self.ip_selecionado = None
        self.predefinicao_widgets = {}
        self.camera_handlers = {}
        self.em_tela_cheia = False
        self.slot_maximized = None
        self.slot_selecionado = 0
        self.ip_seletor_atual = [192, 168, 7, 0]
        self.octet_entries = []
        self.press_data = None
        self.fila_conexoes = queue.Queue()
        self.fila_pendente_conexoes = queue.Queue()
        self.ips_em_fila = set()
        self.cooldown_conexoes = {}
        self.tecla_pressionada = None
        self.ultima_predefinicao = None
        self.aba_ativa = "Câmeras"

        self.carregar_posicao_janela()
        self.predefinicoes = self.carregar_predefinicoes()
        self.ips_unicos = self.carregar_lista_ips()
        self.dados_cameras = self.carregar_config()
        self.grid_cameras = self.carregar_grid()

        # Cache persistente de CTkImage por slot para evitar "pyimage" explosion
        self.slot_ctk_images = [None] * 20
        # Imagem 1x1 transparente para resets seguros
        self.img_vazia = ctk.CTkImage(Image.new('RGBA', (1, 1), (0,0,0,0)), size=(1, 1))

        # Controle da Sidebar
        self.sidebar_visible = True

        # --- LAYOUT ATUALIZADO ---
        self.grid_columnconfigure(0, weight=0) # Sidebar fixa
        self.grid_columnconfigure(1, weight=0) # Botão toggle fixo
        self.grid_columnconfigure(2, weight=1) # Main expande
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar (Coluna 0)
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=self.BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        self.tabview = ctk.CTkTabview(self.sidebar, fg_color="transparent",
                                      segmented_button_selected_color=self.ACCENT_RED,
                                      segmented_button_unselected_hover_color=self.ACCENT_WINE,
                                      text_color=self.TEXT_P)
        self.tabview.pack(expand=True, fill="both", padx=5, pady=5)
        self.tabview.add("Câmeras")
        self.tabview.add("Predefinições")

        # Conteúdo da Sidebar (Câmeras)
        tab_cams = self.tabview.tab("Câmeras")

        # Seletor de IP Manual
        self.criar_seletor_ip(tab_cams)

        self.frame_busca = ctk.CTkFrame(tab_cams, fg_color="transparent")
        self.frame_busca.pack(fill="x", padx=5, pady=5)

        self.entry_busca = ctk.CTkEntry(self.frame_busca, placeholder_text="Filtrar...")
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_busca.bind("<KeyRelease>", lambda e: self.filtrar_lista())

        self.btn_add_cam = ctk.CTkButton(self.frame_busca, text="+", width=35,
                                          fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED,
                                          command=self.abrir_modal_adicionar_camera)
        self.btn_add_cam.pack(side="right")

        self.scroll_frame = ctk.CTkScrollableFrame(tab_cams, fg_color="transparent")
        self.scroll_frame.pack(expand=True, fill="both", padx=0, pady=5)

        # Conteúdo da Sidebar (Predefinições)
        tab_predefinicoes = self.tabview.tab("Predefinições")
        self.btn_salvar_predefinicao = ctk.CTkButton(tab_predefinicoes, text="Salvar Predefinição Atual",
                                                fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED,
                                                command=self.salvar_predefinicao_atual)
        self.btn_salvar_predefinicao.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(tab_predefinicoes, text="LISTA DE PREDEFINIÇÕES", font=("Roboto", 14, "bold"), text_color=self.TEXT_S).pack(pady=5)
        self.scroll_predefinicoes = ctk.CTkScrollableFrame(tab_predefinicoes, fg_color="transparent")
        self.scroll_predefinicoes.pack(expand=True, fill="both", padx=5, pady=5)

        # 2. Container Toggle Sidebar (Coluna 1)
        self.container_toggle = ctk.CTkFrame(self, fg_color=self.BG_PANEL, corner_radius=0)
        self.container_toggle.grid(row=0, column=1, sticky="ns")

        self.lbl_lista_vertical = ctk.CTkLabel(
            self.container_toggle,
            text="L\nI\nS\nT\nA",
            font=("Roboto", 11, "bold"),
            text_color=self.TEXT_S
        )
        self.lbl_lista_vertical.pack(side="left", padx=(2, 0))

        self.btn_toggle_sidebar = ctk.CTkButton(
            self.container_toggle,
            text="◀",
            width=40,
            corner_radius=0,
            font=("Roboto", 24, "bold"),
            fg_color=self.BG_PANEL,
            hover_color=self.ACCENT_WINE,
            text_color=self.ACCENT_RED,
            command=self.toggle_sidebar
        )
        self.btn_toggle_sidebar.pack(side="right", fill="y")

        # 3. Main Frame (Coluna 2)
        self.main_frame = ctk.CTkFrame(self, fg_color=self.BG_MAIN, corner_radius=0)
        self.main_frame.grid(row=0, column=2, sticky="nsew")

        # Grid Frame (Câmeras)
        self.grid_frame = ctk.CTkFrame(self.main_frame, fg_color="#000000")
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=0, pady=0)

        for i in range(4): self.grid_frame.grid_rowconfigure(i, weight=1)
        for i in range(5): self.grid_frame.grid_columnconfigure(i, weight=1)

        # Botões de Controle
        self.btn_expandir = ctk.CTkButton(self.grid_frame, text="Aumentar", width=100, height=35,
                                           fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE,
                                           corner_radius=0, command=self.toggle_grid_layout)

        self.btn_mais_opcoes = ctk.CTkButton(self.grid_frame, text="Mais Opções", width=100, height=35,
                                              fg_color=self.GRAY_DARK, hover_color=self.TEXT_S,
                                              corner_radius=0, command=self.abrir_menu_opcoes)

        self.slot_frames = []
        self.slot_labels = []
        for i in range(20):
            row, col = i // 5, i % 5
            frm = ctk.CTkFrame(self.grid_frame, fg_color=self.BG_SIDEBAR, corner_radius=2, border_width=2, border_color="black")
            frm.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            frm.pack_propagate(False)

            lbl = ctk.CTkLabel(frm, text=f"Espaço {i+1}", corner_radius=0)
            lbl.pack(expand=True, fill="both", padx=2, pady=2)

            for widget in [frm, lbl]:
                widget.bind("<Button-1>", lambda e, idx=i: self.ao_pressionar_slot(e, idx))
                widget.bind("<ButtonRelease-1>", lambda e, idx=i: self.ao_soltar_slot(e, idx))

            self.slot_frames.append(frm)
            self.slot_labels.append(lbl)

        self.atualizar_lista_cameras_ui()
        # Restaura estado inicial
        for i, ip in enumerate(self.grid_cameras):
            if ip and ip != "0.0.0.0":
                # O IP é ocultado por padrão se não selecionado
                self.slot_labels[i].configure(text="AGUARDANDO")

        self.selecionar_slot(self.slot_selecionado)
        self.restaurar_grid()

        # Inicia thread de processamento de conexões staggered
        threading.Thread(target=self._processar_fila_conexoes_pendentes, daemon=True).start()

        self.alternar_todos_streams()
        
        def safe_zoom():
            try: self.state("zoomed")
            except: pass
        self.after(200, safe_zoom)

        self.atualizar_lista_predefinicoes_ui()

        # Restaura estado da interface (aba ativa)
        try:
            if self.aba_ativa in ["Câmeras", "Predefinições"]:
                self.tabview.set(self.aba_ativa)
        except: pass

        # Aplica automaticamente o último predefinição se existir
        if self.ultima_predefinicao and self.ultima_predefinicao in self.predefinicoes:
            self.after(500, lambda: self.aplicar_predefinicao(self.ultima_predefinicao))

        self.loop_exibicao()

    def _processar_fila_conexoes_pendentes(self):
        while True:
            try:
                if not self.fila_pendente_conexoes.empty():
                    ip, canal = self.fila_pendente_conexoes.get()
                    self.ips_em_fila.discard(ip)

                    # Verifica se o IP ainda está no grid
                    if ip not in self.grid_cameras:
                        if self.camera_handlers.get(ip) == "CONECTANDO":
                            del self.camera_handlers[ip]
                        continue

                    # Se já tiver um handler rodando, não faz nada
                    handler = self.camera_handlers.get(ip)
                    if handler and handler != "CONECTANDO" and getattr(handler, 'rodando', False):
                        continue

                    # Se o estado for "CONECTANDO" mas não tivermos o objeto,
                    # significa que este item da fila é o que deve iniciar a thread.
                    # Mas se por algum motivo já houver uma thread, evitamos duplicar.
                    # (Embora ips_em_fila já ajude a evitar duplicados na fila)

                    # Inicia a conexão real
                    # print(f"LOG: Iniciando thread de conexão para {ip} (Queue size: {self.fila_pendente_conexoes.qsize()})")
                    threading.Thread(target=self._thread_conectar, args=(ip, canal), daemon=True).start()

                    # Pausa maior para evitar picos de CPU/Rede durante trocas de predefinicoes
                    time.sleep(0.15)
                else:
                    time.sleep(0.1)
            except Exception as e:
                print(f"Erro no processador de conexões: {e}")
                time.sleep(1)

    # --- LÓGICA DO TOGGLE DA SIDEBAR ---
    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.grid_forget()
            self.btn_toggle_sidebar.configure(text="▶")
            self.sidebar_visible = False
        else:
            self.sidebar.grid(row=0, column=0, sticky="nsew")
            self.btn_toggle_sidebar.configure(text="◀")
            self.sidebar_visible = True

    # --- LÓGICA PTZ ---
    def comando_ptz(self, direcao):
        ip = self.ip_selecionado
        if not ip or ip == "0.0.0.0": return

        if direcao != "STOP":
            if self.tecla_pressionada == direcao: return
            self.tecla_pressionada = direcao
        else:
            self.tecla_pressionada = None

        mapa = {
            "UP": {"pan": 0, "tilt": 100},
            "DOWN": {"pan": 0, "tilt": -100},
            "LEFT": {"pan": -100, "tilt": 0},
            "RIGHT": {"pan": 100, "tilt": 0},
            "STOP": {"pan": 0, "tilt": 0}
        }

        valores = mapa.get(direcao)
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <PTZData xmlns="http://www.isapi.org/ver20/XMLSchema">
            <pan>{valores['pan']}</pan>
            <tilt>{valores['tilt']}</tilt>
        </PTZData>"""

        threading.Thread(target=self._enviar_request_ptz, args=(ip, xml_data), daemon=True).start()

    def _enviar_request_ptz(self, ip, xml):
        url = f"http://{ip}/ISAPI/PTZCtrl/channels/1/continuous"
        try:
            requests.put(
                url,
                data=xml,
                auth=HTTPDigestAuth(self.user_ptz, self.pass_ptz),
                timeout=1
            )
        except Exception as e:
            print(f"Erro PTZ {ip}: {e}")

    # --- TELA CHEIA ATUALIZADO ---
    def entrar_tela_cheia(self):
        if self.em_tela_cheia: return
        self.em_tela_cheia = True
        
        self.sidebar.grid_forget()
        self.container_toggle.grid_forget()

        self.main_frame.grid_configure(column=0, columnspan=3)

        self.grid_frame.pack_forget()
        self.grid_frame.pack(expand=True, fill="both", padx=0, pady=0)
        
        indices_visiveis = [self.slot_maximized] if self.slot_maximized is not None else range(len(self.slot_frames))
        for i, frm in enumerate(self.slot_frames):
            if i in indices_visiveis:
                frm.grid_configure(padx=0, pady=0, sticky="nsew")
                frm.configure(corner_radius=0)
                for child in frm.winfo_children():
                    child.pack_configure(padx=0, pady=0)
            else:
                frm.grid_forget()

        self.btn_sair_fs = ctk.CTkButton(self.main_frame, text="✖ SAIR", width=100, height=40,
                                         fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE, command=self.sair_tela_cheia)
        self.btn_sair_fs.place(relx=0.98, rely=0.02, anchor="ne")
        self.btn_sair_fs.lift()

    def sair_tela_cheia(self):
        if not self.em_tela_cheia: return
        self.em_tela_cheia = False
        if hasattr(self, 'btn_sair_fs'): self.btn_sair_fs.destroy()

        if self.sidebar_visible:
            self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.container_toggle.grid(row=0, column=1, sticky="ns")
        self.main_frame.grid_configure(column=2, columnspan=1)
        
        self.grid_frame.pack_forget()
        padx_grid = 0 if self.slot_maximized is not None else 0
        pady_grid = 0 if self.slot_maximized is not None else 0
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=padx_grid, pady=pady_grid)

        indices_visiveis = [self.slot_maximized] if self.slot_maximized is not None else range(len(self.slot_frames))
        for i, frm in enumerate(self.slot_frames):
            if i in indices_visiveis:
                p = 0 if self.slot_maximized is not None else 1
                p_child = 0 if self.slot_maximized is not None else 2
                rad = 0 if self.slot_maximized is not None else 2
                frm.grid_configure(padx=p, pady=p, sticky="nsew")
                frm.configure(corner_radius=rad)
                for child in frm.winfo_children():
                    child.pack_configure(padx=p_child, pady=p_child)
            else:
                frm.grid_forget()

    def carregar_posicao_janela(self):
        if os.path.exists(self.arquivo_janela):
            try:
                with open(self.arquivo_janela, "r") as f:
                    dados = json.load(f)
                    geom = dados.get("geometry")
                    if geom: self.geometry(geom)
                    self.aba_ativa = dados.get("active_tab", "Câmeras")
                    self.ultima_predefinicao = dados.get("last_predefinicao") or dados.get("last_preset")
                    self.slot_selecionado = dados.get("slot_selecionado", 0)
            except Exception as e: print(f"Erro ao carregar janela: {e}")

    def ao_fechar(self):
        try:
            if not self.em_tela_cheia:
                dados = {
                    "geometry": self.geometry(),
                    "active_tab": self.tabview.get(),
                    "last_predefinicao": self.ultima_predefinicao,
                    "slot_selecionado": self.slot_selecionado
                }
                with open(self.arquivo_janela, "w") as f: json.dump(dados, f)
        except Exception as e: print(f"Erro ao salvar janela: {e}")
        self.destroy()
        os._exit(0)

    def maximizar_slot(self, index):
        self.grid_frame.pack_configure(padx=0, pady=0)

        # IP da câmera que será maximizada
        ip_maximized = self.grid_cameras[index] if index < len(self.grid_cameras) else None

        for i, frm in enumerate(self.slot_frames):
            if i == index:
                frm.grid_configure(row=0, column=0, rowspan=4, columnspan=5, padx=0, pady=0, sticky="nsew")
                frm.configure(corner_radius=0)
                for child in frm.winfo_children(): child.pack_configure(padx=0, pady=0)
            else:
                frm.grid_forget()

        # Gerenciamento de Prioridade e Qualidade
        for ip, handler in self.camera_handlers.items():
            if handler == "CONECTANDO": continue
            if ip == ip_maximized:
                handler.set_prioridade(True)
                handler.set_canal(102) # Mantém Sub Stream (Pedido do Usuário)
            else:
                handler.set_prioridade(False)
                # Opcional: handler.set_canal(102) # Já deve estar em 102

        self.slot_maximized = index
        self.btn_expandir.lift()
        self.btn_mais_opcoes.lift()

    def ao_pressionar_slot(self, event, index):
        self.selecionar_slot(index)
        self.press_data = {"index": index, "x": event.x_root, "y": event.y_root}

    def ao_soltar_slot(self, event, index):
        if not self.press_data: return
        source_idx = self.press_data.get("index")
        if self.slot_maximized is not None or self.em_tela_cheia:
            self.press_data = None
            return
        try:
            dist = ((event.x_root - self.press_data["x"])**2 + (event.y_root - self.press_data["y"])**2)**0.5
            target_idx = self.encontrar_slot_por_coords(event.x_root, event.y_root)

            # Se for apenas um clique (distância pequena) ou soltou fora
            if dist < 15 or target_idx is None:
                return

            # Se arrastou para o mesmo slot
            if target_idx == source_idx:
                return

            # Lógica de Troca (Swap)
            if 0 <= source_idx < 20 and 0 <= target_idx < 20:
                ip_src = self.grid_cameras[source_idx]
                ip_tgt = self.grid_cameras[target_idx]

                # Agora atualiza visualmente e gerencia handlers
                # Note: 'atribuir_ip_ao_slot' agora gerencia 'ultima_predefinicao' internamente
                self.atribuir_ip_ao_slot(source_idx, ip_tgt, atualizar_ui=False)
                self.atribuir_ip_ao_slot(target_idx, ip_src, atualizar_ui=False)

                self.selecionar_slot(target_idx)
                self.update_idletasks()

        finally:
            self.press_data = None

    def encontrar_slot_por_coords(self, x_root, y_root):
        for i, frm in enumerate(self.slot_frames):
            if not frm.winfo_viewable(): continue
            fx, fy = frm.winfo_rootx(), frm.winfo_rooty()
            fw, fh = frm.winfo_width(), frm.winfo_height()
            if fx <= x_root <= fx + fw and fy <= y_root <= fy + fh: return i
        return None

    def restaurar_grid(self):
        self.grid_frame.pack_configure(padx=0, pady=0)

        # IP que estava focado
        ip_foco = self.grid_cameras[self.slot_maximized] if self.slot_maximized is not None else None

        for i, frm in enumerate(self.slot_frames):
            row, col = i // 5, i % 5
            frm.grid_configure(row=row, column=col, rowspan=1, columnspan=1, padx=1, pady=1, sticky="nsew")
            frm.configure(corner_radius=2)
            frm.grid()
            for child in frm.winfo_children(): child.pack_configure(padx=2, pady=2)

        # Gerenciamento de Prioridade e Qualidade (Volta tudo ao normal)
        for ip, handler in self.camera_handlers.items():
            if handler == "CONECTANDO": continue
            handler.set_prioridade(False)
            if ip == ip_foco:
                handler.set_canal(102) # Volta para Sub Stream

        self.slot_maximized = None
        self.btn_expandir.lift()
        self.btn_mais_opcoes.lift()

    def selecionar_slot(self, index):
        if not (0 <= index < 20): return

        # Desliga info de todos os handlers antes de trocar
        for ip_h, h in self.camera_handlers.items():
            if h != "CONECTANDO": h.set_exibir_info(False)

        for frm in self.slot_frames: frm.configure(border_color="black", border_width=2)

        ip_anterior = self.ip_selecionado
        self.slot_selecionado = index
        self.slot_frames[index].configure(border_color=self.ACCENT_RED, border_width=2)

        self.title(f"Monitoramento ABI - Espaço {index + 1} selecionado")

        ip_novo = self.grid_cameras[index]
        if ip_novo and ip_novo != "0.0.0.0":
            if ip_anterior and ip_anterior != ip_novo: self.pintar_botao(ip_anterior, "transparent")
            self.ip_selecionado = ip_novo
            nome = self.dados_cameras.get(ip_novo, "")
            self.pintar_botao(ip_novo, self.ACCENT_WINE)

            # Ativa overlay no handler
            handler = self.camera_handlers.get(ip_novo)
            if handler and handler != "CONECTANDO":
                handler.set_exibir_info(True)

            # Botões de Controle: Aumentar e Mais Opções
            txt_exp = "Diminuir" if self.slot_maximized == index else "Aumentar"
            self.btn_expandir.configure(text=txt_exp)

            # Ordem: Aumentar (Esquerda) | Mais Opções (Direita)
            self.btn_expandir.place(in_=self.slot_frames[index], relx=1.0, rely=1.0, x=-115, y=-10, anchor="se")
            self.btn_mais_opcoes.place(in_=self.slot_frames[index], relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")

            self.btn_expandir.lift()
            self.btn_mais_opcoes.lift()

            # Sincroniza o seletor de IP
            self.sincronizar_seletor_com_ip(ip_novo)
        else:
            if ip_anterior: self.pintar_botao(ip_anterior, "transparent")
            self.ip_selecionado = None
            self.btn_expandir.place_forget()
            self.btn_mais_opcoes.place_forget()
        self.atualizar_botoes_controle()

    def limpar_slot_atual(self):
        self.press_data = None
        idx = self.slot_selecionado
        self.atribuir_ip_ao_slot(idx, "0.0.0.0")

        # Limpa predefinição ao remover manualmente
        if self.ultima_predefinicao:
            self.pintar_predefinicao(self.ultima_predefinicao, self.BG_SIDEBAR)
            self.ultima_predefinicao = None

        if self.ip_selecionado:
            self.pintar_botao(self.ip_selecionado, "transparent")
            self.ip_selecionado = None
        
        self.btn_expandir.place_forget()
        self.btn_mais_opcoes.place_forget()
        
        if self.slot_maximized == idx: self.restaurar_grid()
        self.selecionar_slot(idx)

    def salvar_grid(self):
        try:
            with open(self.arquivo_grid, "w", encoding='utf-8') as f:
                json.dump(self.grid_cameras, f, ensure_ascii=False, indent=4)
        except: pass

    def carregar_grid(self):
        grid = ["0.0.0.0"] * 20
        if os.path.exists(self.arquivo_grid):
            try:
                with open(self.arquivo_grid, "r", encoding='utf-8') as f:
                    dados = json.load(f)
                    if isinstance(dados, list):
                        for i in range(min(len(dados), 20)):
                            if dados[i]: grid[i] = dados[i]
            except: pass
        return grid

    def alternar_todos_streams(self):
        for ip in set(self.grid_cameras):
            if ip and ip != "0.0.0.0" and ip not in self.camera_handlers:
                self.iniciar_conexao_assincrona(ip, 102)

    def atualizar_botoes_controle(self):
        if self.slot_maximized is not None:
            self.btn_expandir.configure(text="Diminuir", width=200, height=70, font=("Roboto", 16, "bold"))
        else:
            self.btn_expandir.configure(text="Aumentar", width=100, height=35, font=("Roboto", 12))

    def toggle_grid_layout(self):
        if self.slot_maximized is not None: self.restaurar_grid()
        else: self.maximizar_slot(self.slot_selecionado)
        self.atualizar_botoes_controle()

    def abrir_menu_opcoes(self):
        if not self.ip_selecionado: return

        nome = self.dados_cameras.get(self.ip_selecionado, "Câmera Sem Nome")
        ip = self.ip_selecionado

        # Cria a janela modal
        modal = ctk.CTkToplevel(self)
        modal.title(f"Opções - {ip}")
        modal.geometry("400x350")
        modal.resizable(False, False)
        modal.attributes("-topmost", True)

        # Tenta centralizar a janela em relação à aplicação
        try:
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 200
            y = self.winfo_y() + (self.winfo_height() // 2) - 175
            modal.geometry(f"+{x}+{y}")
        except: pass

        # Conteúdo
        ctk.CTkLabel(modal, text=nome if nome else "Sem Nome", font=("Roboto", 18, "bold"), text_color=self.TEXT_P).pack(pady=(20, 5))
        ctk.CTkLabel(modal, text=ip, font=("Roboto", 14), text_color=self.TEXT_S).pack(pady=(0, 20))

        # Botões com canto quadrado (corner_radius=0)
        btn_excluir = ctk.CTkButton(modal, text="Excluir", fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE,
                                     corner_radius=0, height=40,
                                     command=lambda: [self.limpar_slot_atual(), modal.destroy()])
        btn_excluir.pack(fill="x", padx=40, pady=5)

        btn_editar = ctk.CTkButton(modal, text="Editar", fg_color=self.GRAY_DARK, hover_color=self.TEXT_S,
                                    corner_radius=0, height=40,
                                    command=lambda: [modal.destroy(), self.alternar_edicao_nome()])
        btn_editar.pack(fill="x", padx=40, pady=5)

        btn_fechar = ctk.CTkButton(modal, text="Fechar", fg_color="#444444", hover_color="#666666",
                                    corner_radius=0, height=40,
                                    command=modal.destroy)
        btn_fechar.pack(fill="x", padx=40, pady=(20, 0))

    def abrir_modal_input(self, titulo, mensagem, callback, valor_inicial=""):
        modal = ctk.CTkToplevel(self)
        modal.title(titulo)
        modal.geometry("400x250")
        modal.resizable(False, False)
        modal.attributes("-topmost", True)

        try:
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 200
            y = self.winfo_y() + (self.winfo_height() // 2) - 125
            modal.geometry(f"+{x}+{y}")
        except: pass

        ctk.CTkLabel(modal, text=mensagem, font=("Roboto", 14, "bold"), text_color=self.TEXT_P).pack(pady=(20, 10))

        entry = ctk.CTkEntry(modal, width=300)
        entry.insert(0, valor_inicial)
        entry.pack(pady=10)
        entry.focus_set()

        def confirmar():
            valor = entry.get()
            modal.destroy()
            callback(valor)

        btn_confirmar = ctk.CTkButton(modal, text="Confirmar", fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE,
                                      corner_radius=0, height=40, command=confirmar)
        btn_confirmar.pack(fill="x", padx=40, pady=5)

        btn_cancelar = ctk.CTkButton(modal, text="Cancelar", fg_color=self.GRAY_DARK, hover_color=self.TEXT_S,
                                     corner_radius=0, height=40, command=modal.destroy)
        btn_cancelar.pack(fill="x", padx=40, pady=5)

        modal.bind("<Return>", lambda e: confirmar())

    def abrir_modal_confirmacao(self, titulo, mensagem, callback_sim):
        modal = ctk.CTkToplevel(self)
        modal.title(titulo)
        modal.geometry("400x200")
        modal.resizable(False, False)
        modal.attributes("-topmost", True)

        try:
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 200
            y = self.winfo_y() + (self.winfo_height() // 2) - 100
            modal.geometry(f"+{x}+{y}")
        except: pass

        ctk.CTkLabel(modal, text=mensagem, font=("Roboto", 14, "bold"), text_color=self.TEXT_P, wraplength=320).pack(pady=(30, 20))

        frame_btns = ctk.CTkFrame(modal, fg_color="transparent")
        frame_btns.pack(fill="x", padx=40)

        btn_sim = ctk.CTkButton(frame_btns, text="Sim", fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE,
                                corner_radius=0, height=40, width=140, command=lambda: [modal.destroy(), callback_sim()])
        btn_sim.pack(side="left", expand=True, padx=5)

        btn_nao = ctk.CTkButton(frame_btns, text="Não", fg_color=self.GRAY_DARK, hover_color=self.TEXT_S,
                                corner_radius=0, height=40, width=140, command=modal.destroy)
        btn_nao.pack(side="right", expand=True, padx=5)

    def abrir_modal_alerta(self, titulo, mensagem):
        modal = ctk.CTkToplevel(self)
        modal.title(titulo)
        modal.geometry("400x180")
        modal.resizable(False, False)
        modal.attributes("-topmost", True)

        try:
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 200
            y = self.winfo_y() + (self.winfo_height() // 2) - 90
            modal.geometry(f"+{x}+{y}")
        except: pass

        ctk.CTkLabel(modal, text=mensagem, font=("Roboto", 14, "bold"), text_color=self.TEXT_P, wraplength=320).pack(pady=(30, 20))

        btn_ok = ctk.CTkButton(modal, text="OK", fg_color=self.GRAY_DARK, hover_color=self.TEXT_S,
                               corner_radius=0, height=40, command=modal.destroy)
        btn_ok.pack(fill="x", padx=60, pady=10)

    def recriar_label_slot(self, idx):
        """Recria o CTkLabel de um slot para limpar estados corrompidos do Tcl/Tkinter."""
        # print(f"LOG: Recriando Label do slot {idx}")
        try:
            # Pega o frame pai
            frm = self.slot_frames[idx]

            # Destrói o label antigo
            if self.slot_labels[idx]:
                try: self.slot_labels[idx].destroy()
                except: pass

            # Cria o novo label
            lbl = ctk.CTkLabel(frm, text=f"Espaço {idx+1}", corner_radius=0)
            lbl.pack(expand=True, fill="both", padx=2, pady=2)

            # Re-bind dos eventos
            lbl.bind("<Button-1>", lambda e, x=idx: self.ao_pressionar_slot(e, x))
            lbl.bind("<ButtonRelease-1>", lambda e, x=idx: self.ao_soltar_slot(e, x))

            self.slot_labels[idx] = lbl
            self.slot_ctk_images[idx] = None
            return lbl
        except Exception as e:
            print(f"ERRO AO RECRIAR LABEL {idx}: {e}")
            return None

    def atribuir_ip_ao_slot(self, idx, ip, atualizar_ui=True, gerenciar_conexoes=True, salvar=True, forcado=False):
        if not (0 <= idx < 20): return

        # Limpa predefinição ao atribuir manualmente (se for uma atribuição direta, não via aplicar_predefinicao)
        # Note: 'aplicar_predefinicao' chama atribuir_ip_ao_slot com gerenciar_conexoes=False
        if gerenciar_conexoes and self.ultima_predefinicao:
            self.pintar_predefinicao(self.ultima_predefinicao, self.BG_SIDEBAR)
            self.ultima_predefinicao = None

        # Otimização: se o IP for o mesmo, não faz nada (a menos que seja 0.0.0.0 ou forçado)
        if not forcado and ip != "0.0.0.0" and self.grid_cameras[idx] == ip:
            return

        ip_antigo = self.grid_cameras[idx]
        self.grid_cameras[idx] = ip
        
        # 1. Limpeza visual ultra-robusta
        # Só mostra IP se for o slot selecionado
        if not ip or ip == "0.0.0.0":
            txt = f"Espaço {idx+1}"
        else:
            txt = f"CONECTANDO...\n{ip}" if idx == self.slot_selecionado else "CONECTANDO..."

        try:
            # Tenta configurar o label existente
            self.slot_labels[idx].configure(image=self.img_vazia, text=txt)
            self.slot_labels[idx].image = self.img_vazia
            # Limpa cache do slot para evitar fantasmas ou falhas de sincronia
            self.slot_ctk_images[idx] = None
        except Exception as e:
            print(f"Erro visual ao atualizar texto slot {idx}: {e}")
            lbl = self.recriar_label_slot(idx)
            if lbl:
                try: lbl.configure(text=txt)
                except: pass

        if atualizar_ui:
            self.update_idletasks()

        if salvar:
            self.salvar_grid()

        # 2. Gerenciamento de conexões (se solicitado)
        if gerenciar_conexoes:
            if ip_antigo and ip_antigo != "0.0.0.0" and ip_antigo != ip and ip_antigo not in self.grid_cameras:
                if ip_antigo in self.camera_handlers:
                    try: self.camera_handlers[ip_antigo].parar()
                    except: pass
                    del self.camera_handlers[ip_antigo]

            if ip != "0.0.0.0":
                if ip in self.cooldown_conexoes: del self.cooldown_conexoes[ip]
                canal_alvo = 102 # Sempre usa Sub Stream
                self.iniciar_conexao_assincrona(ip, canal_alvo)

    def selecionar_camera(self, ip):
        # Esta função é chamada ao clicar na lista lateral
        if self.slot_selecionado is not None:
            self.atribuir_ip_ao_slot(self.slot_selecionado, ip)
            self.selecionar_slot(self.slot_selecionado)

    def pintar_botao(self, ip, cor):
        if ip and ip in self.botoes_referencia: self.botoes_referencia[ip]['frame'].configure(fg_color=cor)

    def pintar_predefinicao(self, nome, cor):
        if nome and nome in self.predefinicao_widgets:
            self.predefinicao_widgets[nome].configure(fg_color=cor)

    def trocar_qualidade(self, ip, novo_canal):
        if not ip: return
        handler = self.camera_handlers.get(ip)
        if handler and handler != "CONECTANDO":
            if getattr(handler, 'canal', 102) != novo_canal:
                handler.parar()
                del self.camera_handlers[ip]
                self.iniciar_conexao_assincrona(ip, novo_canal)

    def formatar_nome(self, nome, max_chars=25):
        if not nome: return ""
        if len(nome) > max_chars: return nome[:max_chars-3] + "..."
        return nome

    def iniciar_conexao_assincrona(self, ip, canal=102):
        if not ip or ip == "0.0.0.0": return
        agora = time.time()

        # Respeita cooldown de falha
        if ip in self.cooldown_conexoes:
            if agora - self.cooldown_conexoes[ip] < 10: return

        # Verifica se já está conectando ou rodando
        if ip in self.camera_handlers:
            handler = self.camera_handlers[ip]
            if handler == "CONECTANDO": return
            if getattr(handler, 'rodando', False): return
            del self.camera_handlers[ip]

        # Evita duplicar na fila
        if ip in self.ips_em_fila: return

        self.camera_handlers[ip] = "CONECTANDO"
        self.ips_em_fila.add(ip)
        self.fila_pendente_conexoes.put((ip, canal))

    def _thread_conectar(self, ip, canal):
        try:
            nova_cam = CameraHandler(ip, canal, user=self.user_ptz, password=self.pass_ptz)
            nova_cam.nome_display = self.dados_cameras.get(ip, "")
            sucesso = nova_cam.iniciar()
            self.fila_conexoes.put((sucesso, nova_cam, ip))
        except Exception as e:
            print(f"Erro crítico na thread de conexão ({ip}): {e}")
            self.fila_conexoes.put((False, None, ip))

    def _pos_conexao(self, sucesso, camera_obj, ip):
        if sucesso:
            # print(f"LOG: Conexão bem-sucedida com {ip}")
            self.camera_handlers[ip] = camera_obj
            if ip in self.cooldown_conexoes: del self.cooldown_conexoes[ip]
        else:
            # print(f"LOG: Falha na conexão final com {ip}")
            if ip in self.camera_handlers: del self.camera_handlers[ip]
            self.cooldown_conexoes[ip] = time.time()
            for i, grid_ip in enumerate(self.grid_cameras):
                if grid_ip == ip:
                    try:
                        self.slot_labels[i].configure(image=None, text=f"FALHA CONEXÃO\n{ip}")
                        self.slot_labels[i].image = None
                        self.slot_ctk_images[i] = None
                    except: pass
        self.atualizar_botoes_controle()

    def loop_exibicao(self):
        try:
            # Processa novas conexões
            while not self.fila_conexoes.empty():
                try:
                    sucesso, camera_obj, ip = self.fila_conexoes.get_nowait()
                    self._pos_conexao(sucesso, camera_obj, ip)
                except: pass

            agora = time.time()
            scaling = self._get_window_scaling()
            indices_trabalho = [self.slot_maximized] if self.slot_maximized is not None else range(20)

            # Mapeia quais IPs estão sendo processados para compartilhar frames se possível (IP -> PIL Image)
            current_ips_pil = {}

            for i in range(20):
                ip = self.grid_cameras[i]

                # Caso o slot deva estar vazio ou não esteja no foco de atualização
                if not ip or ip == "0.0.0.0" or i not in indices_trabalho:
                    # Segurança: se o slot deveria estar vazio, garante texto e imagem vazia
                    if ip == "0.0.0.0":
                        try:
                            target_text = f"Espaço {i+1}"
                            # Verifica se precisa atualizar para evitar cintilação
                            if (self.slot_labels[i].cget("text") != target_text or
                                self.slot_labels[i].image != self.img_vazia):
                                self.slot_labels[i].configure(image=self.img_vazia, text=target_text)
                                self.slot_labels[i].image = self.img_vazia
                                self.slot_ctk_images[i] = None
                        except: pass
                    continue

                # Verifica erro de conexão
                if ip in self.cooldown_conexoes:
                    if agora - self.cooldown_conexoes[ip] < 10:
                        try:
                            target_status = f"FALHA CONEXÃO\n{ip}" if i == self.slot_selecionado else "FALHA CONEXÃO"
                            if self.slot_labels[i].image != self.img_vazia or self.slot_labels[i].cget("text") != target_status:
                                self.slot_labels[i].configure(image=self.img_vazia, text=target_status)
                                self.slot_labels[i].image = self.img_vazia
                                self.slot_ctk_images[i] = None
                        except: pass
                        continue

                handler = self.camera_handlers.get(ip)
                if handler is None:
                    # Decide canal inicial dependendo se está maximizado ou não
                    canal_alvo = 102 # Sempre usa Sub Stream
                    self.iniciar_conexao_assincrona(ip, canal_alvo)
                    continue
                if handler == "CONECTANDO":
                    target_status = f"CONECTANDO...\n{ip}" if i == self.slot_selecionado else "CONECTANDO..."
                    if self.slot_labels[i].cget("text") != target_status:
                        self.slot_labels[i].configure(text=target_status)
                    continue

                try:
                    # Calcula tamanhos físicos
                    wf = self.slot_frames[i].winfo_width()
                    hf = self.slot_frames[i].winfo_height()
                    wf = int(max(10, wf - 6))
                    hf = int(max(10, hf - 6))

                    handler.tamanho_alvo = (wf, hf)
                    handler.interpolation = cv2.INTER_LINEAR if self.slot_maximized == i else cv2.INTER_NEAREST

                    # Verifica se já processamos este IP neste loop
                    pil_img = current_ips_pil.get(ip)
                    if pil_img is None and handler.novo_frame:
                        pil_img = handler.pegar_frame()
                        if pil_img:
                            current_ips_pil[ip] = pil_img

                    if pil_img:
                        wl, hl = wf / scaling, hf / scaling

                        try:
                            # Abordagem de criação direta para garantir atualização (testando se resolve 'dark screen')
                            # Mas mantendo cache para não explodir pyimages
                            if self.slot_ctk_images[i] is None:
                                self.slot_ctk_images[i] = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(wl, hl))
                                # print(f"DEBUG: Slot {i} ({ip}) - Primeiro Frame ({pil_img.size})")
                            else:
                                # Tenta atualizar o objeto existente
                                self.slot_ctk_images[i].configure(light_image=pil_img, dark_image=pil_img, size=(wl, hl))

                            # SEMPRE garante que o label está apontando para o objeto de cache e sem texto
                            if self.slot_labels[i].image != self.slot_ctk_images[i] or self.slot_labels[i].cget("text") != "":
                                self.slot_labels[i].configure(image=self.slot_ctk_images[i], text="")
                                self.slot_labels[i].image = self.slot_ctk_images[i]
                        except Exception as e:
                                # print(f"DEBUG: Erro ao renderizar frame no slot {i}: {e}")
                                # Se falhar muito, tentamos recriar o cache do slot
                                self.slot_ctk_images[i] = None
                    else:
                        # Stream aberto mas sem frames (pode estar carregando ou com erro de codec)
                        # if i % 100 == 0: # Log esparso para não inundar
                        #     print(f"DEBUG: Slot {i} ({ip}) - Aguardando frame válido...")
                        pass

                except Exception as e:
                    # print(f"Erro render slot {i}: {e}")
                    pass

            if self.btn_expandir.winfo_ismapped():
                self.btn_expandir.lift()
            if self.btn_mais_opcoes.winfo_ismapped():
                self.btn_mais_opcoes.lift()

        except Exception as e: print(f"Erro no loop de exibição: {e}")
        finally: self.after(60, self.loop_exibicao) # Aumentado de 40 para 60 para aliviar thread principal

    def filtrar_lista(self):
        termo = self.entry_busca.get().lower()
        for item in self.botoes_referencia.values(): item['frame'].pack_forget()
        for ip in self.obter_ips_ordenados():
            item = self.botoes_referencia.get(ip)
            if not item: continue
            nome = self.dados_cameras.get(ip, "").lower()
            if termo in ip or termo in nome: item['frame'].pack(fill="x", pady=2)
        try:
            if hasattr(self.scroll_frame, "_parent_canvas"): self.scroll_frame._parent_canvas.yview_moveto(0)
        except: pass

    def alternar_edicao_nome(self):
        if not self.ip_selecionado: return
        self.abrir_modal_input("Renomear Câmera", "Digite o novo nome para a câmera:",
                               self.salvar_nome, valor_inicial=self.dados_cameras.get(self.ip_selecionado, ""))

    def salvar_nome(self, novo_nome):
        if self.ip_selecionado:
            self.dados_cameras[self.ip_selecionado] = novo_nome
            with open(self.arquivo_config, "w", encoding='utf-8') as f:
                json.dump(self.dados_cameras, f, ensure_ascii=False, indent=4)

            # Atualiza handler se existir
            handler = self.camera_handlers.get(self.ip_selecionado)
            if handler and handler != "CONECTANDO":
                handler.nome_display = novo_nome

            # Atualiza UI se estiver visível
            if self.ip_selecionado in self.botoes_referencia:
                self.botoes_referencia[self.ip_selecionado]['lbl_nome'].configure(text=novo_nome)
            self.filtrar_lista()

    def abrir_modal_adicionar_camera(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Adicionar Câmera")
        modal.geometry("400x350")
        modal.resizable(False, False)
        modal.attributes("-topmost", True)

        try:
            self.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 200
            y = self.winfo_y() + (self.winfo_height() // 2) - 175
            modal.geometry(f"+{x}+{y}")
        except: pass

        ctk.CTkLabel(modal, text="Adicionar Nova Câmera", font=("Roboto", 16, "bold")).pack(pady=20)

        ctk.CTkLabel(modal, text="IP da Câmera:").pack()
        entry_ip = ctk.CTkEntry(modal, width=300, placeholder_text="Ex: 192.168.7.50")
        entry_ip.pack(pady=5)

        ctk.CTkLabel(modal, text="Nome da Câmera:").pack()
        entry_nome = ctk.CTkEntry(modal, width=300, placeholder_text="Ex: Portão Principal")
        entry_nome.pack(pady=5)

        def confirmar():
            ip = entry_ip.get().strip()
            nome = entry_nome.get().strip()
            if not ip:
                self.abrir_modal_alerta("Erro", "O IP é obrigatório.")
                return
            modal.destroy()
            self.adicionar_camera_confirmado(ip, nome)

        btn_conf = ctk.CTkButton(modal, text="Confirmar", fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE,
                                  corner_radius=0, height=40, command=confirmar)
        btn_conf.pack(fill="x", padx=40, pady=20)

        btn_canc = ctk.CTkButton(modal, text="Cancelar", fg_color=self.GRAY_DARK, hover_color=self.TEXT_S,
                                  corner_radius=0, height=40, command=modal.destroy)
        btn_canc.pack(fill="x", padx=40)

        modal.bind("<Return>", lambda e: confirmar())

    def adicionar_camera_confirmado(self, ip, nome):
        if ip in self.ips_unicos:
            self.abrir_modal_alerta("Aviso", "Este IP já existe na lista.")
            return

        self.ips_unicos.append(ip)
        # Ordena a lista
        self.ips_unicos.sort(key=lambda x: [int(d) if d.isdigit() else 0 for d in x.split('.')])

        if nome:
            self.dados_cameras[ip] = nome
            with open(self.arquivo_config, "w", encoding='utf-8') as f:
                json.dump(self.dados_cameras, f, ensure_ascii=False, indent=4)

        self.salvar_lista_ips()
        self.atualizar_lista_cameras_ui()
        self.filtrar_lista()

    def confirmar_exclusao_camera_da_lista(self, ip):
        self.abrir_modal_confirmacao("Excluir Câmera", f"Deseja remover o IP {ip} da lista de câmeras?",
                                     lambda: self.excluir_camera_da_lista(ip))

    def excluir_camera_da_lista(self, ip):
        if ip in self.ips_unicos:
            self.ips_unicos.remove(ip)
            if ip in self.dados_cameras:
                del self.dados_cameras[ip]
                with open(self.arquivo_config, "w", encoding='utf-8') as f:
                    json.dump(self.dados_cameras, f, ensure_ascii=False, indent=4)

            self.salvar_lista_ips()
            self.atualizar_lista_cameras_ui()
            self.filtrar_lista()

    def gerar_lista_ips(self):
        base = ["192.168.7.2", "192.168.7.3", "192.168.7.4", "192.168.7.20", "192.168.7.21",
                "192.168.7.22", "192.168.7.23", "192.168.7.24", "192.168.7.26", "192.168.7.27",
                "192.168.7.31", "192.168.7.32", "192.168.7.33", "192.168.7.35", "192.168.7.37",
                "192.168.7.39", "192.168.7.43", "192.168.7.78", "192.168.7.79", "192.168.7.81",
                "192.168.7.89", "192.168.7.92", "192.168.7.94", "192.168.7.98", "192.168.7.99"]
        base += [f"192.168.7.{i}" for i in range(100, 216)]
        base += ["192.168.7.237", "192.168.7.246", "192.168.7.247", "192.168.7.248", "192.168.7.249",
                 "192.168.7.250", "192.168.7.251", "192.168.7.252"]
        ips = sorted(list(set(base)), key=lambda x: [int(d) for d in x.split('.')])
        return ips

    def carregar_lista_ips(self):
        if os.path.exists(self.arquivo_ips):
            try:
                with open(self.arquivo_ips, "r", encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        ips = self.gerar_lista_ips()
        self.salvar_lista_ips(ips)
        return ips

    def salvar_lista_ips(self, ips=None):
        if ips is None: ips = self.ips_unicos
        try:
            with open(self.arquivo_ips, "w", encoding='utf-8') as f:
                json.dump(ips, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao salvar lista de IPs: {e}")

    def carregar_config(self):
        if os.path.exists(self.arquivo_config):
            try:
                with open(self.arquivo_config, "r", encoding='utf-8') as f: return json.load(f)
            except: pass
        return {}

    def obter_ips_ordenados(self):
        def chave_ordenacao(ip): return self.dados_cameras.get(ip, f"IP {ip}").lower()
        return sorted(self.ips_unicos, key=chave_ordenacao)

    def criar_seletor_ip(self, parent):
        frame_seletor = ctk.CTkFrame(parent, fg_color="transparent")
        frame_seletor.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_seletor, text="SELETOR DE IP", font=("Roboto", 12, "bold"), text_color=self.TEXT_S).pack(pady=(0, 5))

        container_octetos = ctk.CTkFrame(frame_seletor, fg_color="transparent")
        container_octetos.pack()

        self.octet_entries = []
        for i in range(4):
            col = ctk.CTkFrame(container_octetos, fg_color="transparent")
            col.pack(side="left")

            btn_up = ctk.CTkButton(col, text="▲", width=35, height=25, fg_color=self.GRAY_DARK, hover_color=self.ACCENT_RED,
                                   corner_radius=4, command=lambda idx=i: self.alterar_octeto(idx, 1))
            btn_up.pack(pady=2)

            ent = ctk.CTkEntry(col, width=45, font=("Roboto", 14, "bold"), justify="center")
            ent.insert(0, str(self.ip_seletor_atual[i]))
            ent.pack(pady=2)
            ent.bind("<KeyRelease>", lambda e, idx=i: self.ao_digitar_octeto(e, idx))
            ent.bind("<Return>", lambda e, idx=i: self.confirmar_digitacao_octeto(idx))
            self.octet_entries.append(ent)

            btn_down = ctk.CTkButton(col, text="▼", width=35, height=25, fg_color=self.GRAY_DARK, hover_color=self.ACCENT_RED,
                                     corner_radius=4, command=lambda idx=i: self.alterar_octeto(idx, -1))
            btn_down.pack(pady=2)

            if i < 3:
                ctk.CTkLabel(container_octetos, text=".", font=("Roboto", 20, "bold")).pack(side="left", padx=2, pady=(25, 0))

    def alterar_octeto(self, idx, delta):
        self.ip_seletor_atual[idx] = (self.ip_seletor_atual[idx] + delta) % 256
        self.atualizar_labels_seletor()

        # Se houver um slot selecionado, atualiza o IP dele
        if self.slot_selecionado is not None:
            novo_ip = ".".join(map(str, self.ip_seletor_atual))
            self.atribuir_ip_ao_slot(self.slot_selecionado, novo_ip)

    def ao_digitar_octeto(self, event, idx):
        val_str = self.octet_entries[idx].get()
        if val_str.isdigit():
            val = int(val_str)
            if 0 <= val <= 255:
                self.ip_seletor_atual[idx] = val
                if self.slot_selecionado is not None:
                    novo_ip = ".".join(map(str, self.ip_seletor_atual))
                    self.atribuir_ip_ao_slot(self.slot_selecionado, novo_ip, salvar=False) # Não salva em cada tecla

    def confirmar_digitacao_octeto(self, idx):
        val_str = self.octet_entries[idx].get()
        if val_str.isdigit():
            val = int(val_str)
            if 0 <= val <= 255:
                self.ip_seletor_atual[idx] = val
                if self.slot_selecionado is not None:
                    novo_ip = ".".join(map(str, self.ip_seletor_atual))
                    self.atribuir_ip_ao_slot(self.slot_selecionado, novo_ip, salvar=True)
        self.atualizar_labels_seletor()

    def atualizar_labels_seletor(self):
        for i, val in enumerate(self.ip_seletor_atual):
            if i < len(self.octet_entries):
                self.octet_entries[i].delete(0, "end")
                self.octet_entries[i].insert(0, str(val))

    def sincronizar_seletor_com_ip(self, ip):
        if not ip or ip == "0.0.0.0":
            return

        try:
            partes = ip.split('.')
            if len(partes) == 4:
                self.ip_seletor_atual = [int(p) for p in partes]
                self.atualizar_labels_seletor()
        except:
            pass

    def atualizar_lista_cameras_ui(self):
        for child in self.scroll_frame.winfo_children():
            child.destroy()
        self.botoes_referencia = {}

        for ip in self.obter_ips_ordenados():
            nome = self.dados_cameras.get(ip, f"IP {ip}")
            cor = self.ACCENT_WINE if ip == self.ip_selecionado else "transparent"
            frm = ctk.CTkFrame(self.scroll_frame, height=50, fg_color=cor, border_width=1, border_color=self.GRAY_DARK)
            frm.pack(fill="x", pady=2); frm.pack_propagate(False)

            # Container para o texto (Label)
            txt_container = ctk.CTkFrame(frm, fg_color="transparent")
            txt_container.pack(side="left", fill="both", expand=True)

            lbl_nome = ctk.CTkLabel(txt_container, text=nome, font=("Roboto", 13, "bold"), text_color=self.TEXT_P, anchor="w")
            lbl_nome.pack(fill="x", padx=10, pady=(4, 0))
            lbl_ip = ctk.CTkLabel(txt_container, text=ip, font=("Roboto", 11), text_color=self.TEXT_S, anchor="w")
            lbl_ip.pack(fill="x", padx=10, pady=(0, 4))

            # Botão de Deletar
            btn_del = ctk.CTkButton(frm, text="X", width=30, height=30, fg_color="transparent",
                                     text_color=self.TEXT_S, hover_color=self.ACCENT_RED,
                                     command=lambda x=ip: self.confirmar_exclusao_camera_da_lista(x))
            btn_del.pack(side="right", padx=5)

            for widget in [txt_container, lbl_nome, lbl_ip]:
                widget.bind("<Button-1>", lambda e, x=ip: self.selecionar_camera(x))
                widget.configure(cursor="hand2")

            self.botoes_referencia[ip] = {'frame': frm, 'lbl_nome': lbl_nome, 'lbl_ip': lbl_ip}

    # --- MÉTODOS DE PREDEFINIÇÕES ---
    def carregar_predefinicoes(self):
        if os.path.exists(self.arquivo_predefinicoes):
            try:
                with open(self.arquivo_predefinicoes, "r", encoding='utf-8') as f:
                    return json.load(f)
            except: pass

        # Migração de legado
        user_dir = os.path.expanduser("~")
        arquivo_legado = os.path.join(user_dir, "presets_grid_abi.json")
        if os.path.exists(arquivo_legado):
            try:
                with open(arquivo_legado, "r", encoding='utf-8') as f:
                    dados = json.load(f)
                    # Salva no novo local imediatamente
                    with open(self.arquivo_predefinicoes, "w", encoding='utf-8') as f_new:
                        json.dump(dados, f_new, ensure_ascii=False, indent=4)
                    return dados
            except: pass

        return {}

    def salvar_predefinicoes(self):
        try:
            with open(self.arquivo_predefinicoes, "w", encoding='utf-8') as f:
                json.dump(self.predefinicoes, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao salvar predefinicoes: {e}")

    def salvar_predefinicao_atual(self):
        def on_name_entered(nome):
            nome = nome.strip()
            if not nome:
                self.abrir_modal_alerta("Erro", "O nome da predefinição não pode ser vazio.")
                return

            if nome in self.predefinicoes:
                self.abrir_modal_confirmacao("Confirmar", f"A predefinição '{nome}' já existe. Deseja sobrescrevê-la?",
                                                lambda: self._salvar_predefinicao(nome))
            else:
                self._salvar_predefinicao(nome)

        self.abrir_modal_input("Salvar Predefinição", "Digite um nome para esta predefinição:", on_name_entered)

    def _salvar_predefinicao(self, nome):
        self.predefinicoes[nome] = list(self.grid_cameras)
        self.ultima_predefinicao = nome
        self.salvar_predefinicoes()
        self.atualizar_lista_predefinicoes_ui()

    def aplicar_predefinicao(self, nome):
        predefinicao = self.predefinicoes.get(nome)
        if not predefinicao: return

        # Limpa o cooldown para permitir reconexão imediata se for um predefinicao
        self.cooldown_conexoes.clear()

        # Gerencia cores na lista de predefinicoes
        if self.ultima_predefinicao:
            self.pintar_predefinicao(self.ultima_predefinicao, self.BG_SIDEBAR)
        self.ultima_predefinicao = nome
        self.pintar_predefinicao(nome, self.ACCENT_WINE)

        # print(f"Aplicando predefinição: {nome}")

        # 1. Mapeia IPs atuais para saber o que fechar depois
        ips_antigos = set(ip for ip in self.grid_cameras if ip and ip != "0.0.0.0")

        # 2. Atualiza os dados do grid primeiro (silenciosamente)
        novos_ips = ["0.0.0.0"] * 20
        for i in range(20):
            ip = predefinicao[i] if i < len(predefinicao) else "0.0.0.0"
            novos_ips[i] = ip

            # Atualiza visualmente cada slot de forma segura
            self.atribuir_ip_ao_slot(i, ip, atualizar_ui=False, gerenciar_conexoes=False, salvar=False)

        self.salvar_grid()

        # 3. Identifica IPs que não estão mais no grid e fecha-os
        ips_novos_set = set(ip for ip in novos_ips if ip and ip != "0.0.0.0")
        for ip_off in (ips_antigos - ips_novos_set):
            if ip_off in self.camera_handlers:
                try:
                    h = self.camera_handlers[ip_off]
                    if hasattr(h, 'parar'): h.parar()
                except: pass
                del self.camera_handlers[ip_off]

        # 4. Inicia conexões para os novos IPs (o staggered cuidará do resto)
        for ip in ips_novos_set:
            self.iniciar_conexao_assincrona(ip, 102)

        # 5. Restaura layout se necessário e seleciona slot
        if self.slot_maximized is not None:
            self.restaurar_grid()

        self.selecionar_slot(self.slot_selecionado)
        self.update_idletasks()
        # print(f"Predefinição '{nome}' aplicada!")

    def sobrescrever_predefinicao(self, nome):
        self.abrir_modal_confirmacao("Confirmar", f"Deseja sobrescrever o predefinição '{nome}' com a configuração atual?",
                                     lambda: self._sobrescrever_predefinicao(nome))

    def _sobrescrever_predefinicao(self, nome):
        self.predefinicoes[nome] = list(self.grid_cameras)
        self.salvar_predefinicoes()
        self.ultima_predefinicao = nome
        self.atualizar_lista_predefinicoes_ui()

    def deletar_predefinicao(self, nome):
        self.abrir_modal_confirmacao("Confirmar", f"Deseja realmente excluir o predefinição '{nome}'?",
                                     lambda: self._deletar_predefinicao(nome))

    def _deletar_predefinicao(self, nome):
        if nome in self.predefinicoes:
            del self.predefinicoes[nome]
            if self.ultima_predefinicao == nome:
                self.ultima_predefinicao = None
            self.salvar_predefinicoes()
            self.atualizar_lista_predefinicoes_ui()

    def renomear_predefinicao(self, nome_antigo):
        def on_name_entered(novo_nome):
            novo_nome = novo_nome.strip()
            if not novo_nome:
                self.abrir_modal_alerta("Erro", "O nome da predefinição não pode ser vazio.")
                return

            if novo_nome and novo_nome != nome_antigo:
                if novo_nome in self.predefinicoes:
                    self.abrir_modal_alerta("Erro", "Já existe uma predefinição com este nome.")
                    return

                if nome_antigo in self.predefinicoes:
                    self.predefinicoes[novo_nome] = self.predefinicoes.pop(nome_antigo)
                    if self.ultima_predefinicao == nome_antigo:
                        self.ultima_predefinicao = novo_nome
                    self.salvar_predefinicoes()
                    self.atualizar_lista_predefinicoes_ui()

        self.abrir_modal_input("Renomear Predefinição", f"Novo nome para '{nome_antigo}':",
                               on_name_entered, valor_inicial=nome_antigo)

    def atualizar_lista_predefinicoes_ui(self):
        for child in self.scroll_predefinicoes.winfo_children():
            child.destroy()
        self.predefinicao_widgets = {}

        for nome in sorted(self.predefinicoes.keys(), key=str.lower):
            cor = self.ACCENT_WINE if nome == self.ultima_predefinicao else self.BG_SIDEBAR
            frm = ctk.CTkFrame(self.scroll_predefinicoes, height=50, fg_color=cor, border_width=1, border_color=self.GRAY_DARK)
            frm.pack(fill="x", pady=2, padx=2)
            frm.pack_propagate(False)

            # Bind no Frame para facilitar o clique
            frm.bind("<Button-1>", lambda e, n=nome: self.aplicar_predefinicao(n))
            frm.configure(cursor="hand2")

            # Botões de Controle (Ordem: X, ✎, 💾 - pack no lado direito)
            btn_del = ctk.CTkButton(frm, text="X", width=30, height=30, fg_color="transparent",
                                     text_color=self.TEXT_S, hover_color=self.ACCENT_RED,
                                     command=lambda n=nome: self.deletar_predefinicao(n))
            btn_del.pack(side="right", padx=5)

            btn_ren = ctk.CTkButton(frm, text="✎", width=30, height=30, fg_color="transparent",
                                     text_color=self.TEXT_S, hover_color=self.GRAY_DARK,
                                     command=lambda n=nome: self.renomear_predefinicao(n))
            btn_ren.pack(side="right", padx=2)

            btn_save = ctk.CTkButton(frm, text="💾", width=30, height=30, fg_color="transparent",
                                      text_color=self.TEXT_S, hover_color=self.GRAY_DARK,
                                      command=lambda n=nome: self.sobrescrever_predefinicao(n))
            btn_save.pack(side="right", padx=2)

            # Label de Nome (Expandível)
            lbl = ctk.CTkLabel(frm, text=nome, font=("Roboto", 13, "bold"), text_color=self.TEXT_P, anchor="w", cursor="hand2")
            lbl.pack(side="left", expand=True, fill="both", padx=10)
            lbl.bind("<Button-1>", lambda e, n=nome: self.aplicar_predefinicao(n))

            self.predefinicao_widgets[nome] = frm

if __name__ == "__main__":
    app = CentralMonitoramento()
    app.mainloop()
