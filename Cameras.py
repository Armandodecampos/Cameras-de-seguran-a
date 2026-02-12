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
from tkinter import messagebox, simpledialog

# Configuração de baixa latência para OpenCV/FFMPEG
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp;analyzeduration;50000;probesize;50000;fflags;nobuffer;flags;low_delay;max_delay;0;bf;0"
cv2.setNumThreads(0)

# --- CLASSE DE VÍDEO OTIMIZADA ---
class CameraHandler:
    def __init__(self, url, canal=101):
        self.url = url
        self.canal = canal
        self.cap = None
        self.rodando = False
        self.frame_pil = None
        self.lock = threading.Lock()
        self.conectado = False
        self.tamanho_alvo = (640, 480)
        self.interpolation = cv2.INTER_NEAREST
        self.ip_display = url.split('@')[-1].split(':')[0] if '@' in url else "Camera"

    def iniciar(self):
        try:
            print(f"Tentando conectar em: {self.ip_display}...")
            self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

            # Tenta forçar timeout de 5s na conexão se o driver e a versão do cv2 suportarem
            if hasattr(cv2, 'CAP_PROP_OPEN_TIMEOUT_USEC'):
                try: self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_USEC, 5000000)
                except: pass

            # Tenta definir buffer size de forma segura
            if hasattr(cv2, 'CAP_PROP_BUFFERSIZE'):
                try: self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
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
        while self.rodando and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                consecutive_failures = 0
                try:
                    w, h = self.tamanho_alvo
                    # Garante que w e h sejam inteiros para evitar erro no resize
                    w, h = int(w), int(h)
                    
                    # Redimensiona apenas se necessário para economizar CPU
                    if frame.shape[1] != w or frame.shape[0] != h:
                        frame_res = cv2.resize(frame, (w, h), interpolation=self.interpolation)
                    else:
                        frame_res = frame

                    # Adiciona timestamp ou IP para debug visual
                    cv2.putText(frame_res, self.ip_display, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
                    cv2.putText(frame_res, self.ip_display, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
                    
                    rgb = cv2.cvtColor(frame_res, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb)
                    
                    with self.lock:
                        self.frame_pil = pil_img
                except Exception as e:
                    # print(f"Erro processamento frame: {e}")
                    time.sleep(0.01)
            else:
                consecutive_failures += 1
                if consecutive_failures > 100: # ~1-2 segundos sem frames
                    # print(f"LOG: Camera {self.ip_display} parou de enviar frames.")
                    break
                time.sleep(0.01)

        if self.cap:
            self.cap.release()
        self.rodando = False
        self.conectado = False

    def pegar_frame(self):
        with self.lock:
            return self.frame_pil

    def parar(self):
        self.rodando = False
        self.conectado = False

# --- INTERFACE PRINCIPAL ---
class CentralMonitoramento(ctk.CTk):
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
        self.arquivo_presets = os.path.join(user_dir, "presets_grid_abi.json")

        self.botoes_referencia = {}
        self.ip_selecionado = None
        self.preset_widgets = {}
        self.camera_handlers = {}
        self.em_tela_cheia = False
        self.slot_maximized = None
        self.slot_selecionado = 0
        self.press_data = None
        self.fila_conexoes = queue.Queue()
        self.fila_pendente_conexoes = queue.Queue()
        self.ips_em_fila = set()
        self.cooldown_conexoes = {}
        self.tecla_pressionada = None
        self.ultimo_preset = None
        self.aba_ativa = "Câmeras"

        self.carregar_posicao_janela()
        self.presets = self.carregar_presets()
        self.ips_unicos = self.gerar_lista_ips()
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
        self.frame_busca = ctk.CTkFrame(tab_cams, fg_color="transparent")
        self.frame_busca.pack(fill="x", padx=5, pady=5)

        self.entry_busca = ctk.CTkEntry(self.frame_busca, placeholder_text="Filtrar...")
        self.entry_busca.pack(fill="x", expand=True)
        self.entry_busca.bind("<KeyRelease>", lambda e: self.filtrar_lista())

        self.scroll_frame = ctk.CTkScrollableFrame(tab_cams, fg_color="transparent")
        self.scroll_frame.pack(expand=True, fill="both", padx=0, pady=5)

        # Conteúdo da Sidebar (Presets)
        tab_presets = self.tabview.tab("Predefinições")
        self.btn_salvar_preset = ctk.CTkButton(tab_presets, text="Salvar Predefinição Atual",
                                                fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED,
                                                command=self.salvar_preset_atual)
        self.btn_salvar_preset.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(tab_presets, text="LISTA DE PREDEFINIÇÕES", font=("Roboto", 14, "bold"), text_color=self.TEXT_S).pack(pady=5)
        self.scroll_presets = ctk.CTkScrollableFrame(tab_presets, fg_color="transparent")
        self.scroll_presets.pack(expand=True, fill="both", padx=5, pady=5)

        # 2. Botão Toggle Sidebar (Coluna 1)
        self.btn_toggle_sidebar = ctk.CTkButton(
            self, 
            text="<", 
            width=40,
            corner_radius=0,
            font=("Roboto", 16, "bold"),
            fg_color=self.BG_PANEL, 
            hover_color=self.ACCENT_WINE,
            command=self.toggle_sidebar
        )
        self.btn_toggle_sidebar.grid(row=0, column=1, sticky="ns", padx=0, pady=0)

        # 3. Main Frame (Coluna 2)
        self.main_frame = ctk.CTkFrame(self, fg_color=self.BG_MAIN, corner_radius=0)
        self.main_frame.grid(row=0, column=2, sticky="nsew")

        # Painel Topo
        self.painel_topo = ctk.CTkFrame(self.main_frame, fg_color=self.BG_PANEL, height=40)
        self.painel_topo.pack(side="top", fill="x", padx=0, pady=0)

        self.container_info_topo = ctk.CTkFrame(self.painel_topo, fg_color="transparent")
        self.container_info_topo.pack(side="left", padx=10, pady=2)

        self.lbl_nome_topo = ctk.CTkLabel(self.container_info_topo, text="Nenhuma câmera selecionada",
                                          font=("Roboto", 15, "bold"), text_color=self.ACCENT_RED)
        self.lbl_nome_topo.pack(side="left")

        self.lbl_ip_topo = ctk.CTkLabel(self.container_info_topo, text="",
                                        font=("Roboto", 13), text_color=self.TEXT_S)
        self.lbl_ip_topo.pack(side="left", padx=(5, 0))

        self.btn_limpar_slot = ctk.CTkButton(self.painel_topo, text="Remover", command=self.limpar_slot_atual,
                                             fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE, width=120)
        self.btn_limpar_slot.pack(side="right", padx=5)

        self.btn_renomear = ctk.CTkButton(self.painel_topo, text="Renomear", command=self.alternar_edicao_nome,
                                        fg_color=self.GRAY_DARK, hover_color=self.TEXT_S, width=100, state="disabled")
        self.btn_renomear.pack(side="right", padx=5)

        self.entry_nome = ctk.CTkEntry(self.painel_topo, width=300, placeholder_text="Nome da câmera...")

        # Grid Frame (Câmeras)
        self.grid_frame = ctk.CTkFrame(self.main_frame, fg_color="#000000")
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=0, pady=0)

        for i in range(4): self.grid_frame.grid_rowconfigure(i, weight=1)
        for i in range(5): self.grid_frame.grid_columnconfigure(i, weight=1)

        # Botão Aumentar/Diminuir
        self.btn_expandir = ctk.CTkButton(self.grid_frame, text="Aumentar", width=100, height=35,
                                           fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE,
                                           command=self.toggle_grid_layout)

        self.slot_frames = []
        self.slot_labels = []
        for i in range(20):
            row, col = i // 5, i % 5
            frm = ctk.CTkFrame(self.grid_frame, fg_color=self.BG_SIDEBAR, corner_radius=2, border_width=2, border_color="black")
            frm.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            frm.pack_propagate(False)

            lbl = ctk.CTkLabel(frm, text=f"Espaço {i+1}", corner_radius=0)
            lbl.pack(expand=True, fill="both", padx=2, pady=2)

            frm.bind("<Button-1>", lambda e, idx=i: self.ao_pressionar_slot(e, idx))
            lbl.bind("<Button-1>", lambda e, idx=i: self.ao_pressionar_slot(e, idx))
            frm.bind("<ButtonRelease-1>", lambda e, idx=i: self.ao_soltar_slot(e, idx))
            lbl.bind("<ButtonRelease-1>", lambda e, idx=i: self.ao_soltar_slot(e, idx))

            self.slot_frames.append(frm)
            self.slot_labels.append(lbl)

        self.criar_botoes_iniciais()
        # Restaura estado inicial
        for i, ip in enumerate(self.grid_cameras):
            if ip and ip != "0.0.0.0": 
                self.slot_labels[i].configure(text=f"AGUARDANDO\n{ip}")

        self.selecionar_slot(self.slot_selecionado)
        self.restaurar_grid()

        # Inicia thread de processamento de conexões staggered
        threading.Thread(target=self._processar_fila_conexoes_pendentes, daemon=True).start()

        self.alternar_todos_streams()
        
        try:
            self.after(200, lambda: self.state("zoomed"))
        except:
            pass # Ignora erro se não suportar zoomed (ex: Linux/Mac às vezes)
            
        self.atualizar_lista_presets_ui()

        # Restaura estado da interface (aba ativa)
        try:
            if self.aba_ativa in ["Câmeras", "Predefinições"]:
                self.tabview.set(self.aba_ativa)
        except: pass

        # Aplica automaticamente o último preset se existir
        if self.ultimo_preset and self.ultimo_preset in self.presets:
            self.after(500, lambda: self.aplicar_preset(self.ultimo_preset))

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

                    # Pausa menor para maior agilidade, mas ainda staggered
                    time.sleep(0.05)
                else:
                    time.sleep(0.05)
            except Exception as e:
                print(f"Erro no processador de conexões: {e}")
                time.sleep(1)

    # --- LÓGICA DO TOGGLE DA SIDEBAR ---
    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.grid_forget()
            self.btn_toggle_sidebar.configure(text=">")
            self.sidebar_visible = False
        else:
            self.sidebar.grid(row=0, column=0, sticky="nsew")
            self.btn_toggle_sidebar.configure(text="<")
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
        self.btn_toggle_sidebar.grid_forget()

        self.main_frame.grid_configure(column=0, columnspan=3)
        self.painel_topo.pack_forget()
        
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
        
        self.btn_toggle_sidebar.grid(row=0, column=1, sticky="ns")
        self.main_frame.grid_configure(column=2, columnspan=1)
        
        self.painel_topo.pack(side="top", fill="x", padx=0, pady=0)
        
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
                    self.ultimo_preset = dados.get("last_preset")
                    self.slot_selecionado = dados.get("slot_selecionado", 0)
            except Exception as e: print(f"Erro ao carregar janela: {e}")

    def ao_fechar(self):
        try:
            if not self.em_tela_cheia:
                dados = {
                    "geometry": self.geometry(),
                    "active_tab": self.tabview.get(),
                    "last_preset": self.ultimo_preset,
                    "slot_selecionado": self.slot_selecionado
                }
                with open(self.arquivo_janela, "w") as f: json.dump(dados, f)
        except Exception as e: print(f"Erro ao salvar janela: {e}")
        self.destroy()
        os._exit(0)

    def maximizar_slot(self, index):
        self.grid_frame.pack_configure(padx=0, pady=0)
        for i, frm in enumerate(self.slot_frames):
            if i == index:
                frm.grid_configure(row=0, column=0, rowspan=4, columnspan=5, padx=0, pady=0, sticky="nsew")
                frm.configure(corner_radius=0)
                for child in frm.winfo_children(): child.pack_configure(padx=0, pady=0)
            else:
                frm.grid_forget()
        self.slot_maximized = index
        ip = self.grid_cameras[index]
        if ip: self.trocar_qualidade(ip, 101)
        self.btn_expandir.lift()

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
                # Limpa preset ao trocar manualmente
                if self.ultimo_preset:
                    self.pintar_preset(self.ultimo_preset, self.BG_SIDEBAR)
                    self.ultimo_preset = None

                ip_src = self.grid_cameras[source_idx]
                ip_tgt = self.grid_cameras[target_idx]
                
                # Atualiza a estrutura de dados primeiro para evitar que conexões
                # ativas sejam fechadas durante a troca (swap)
                self.grid_cameras[source_idx] = ip_tgt
                self.grid_cameras[target_idx] = ip_src

                # Agora atualiza visualmente e gerencia handlers se necessário
                self.atribuir_ip_ao_slot(source_idx, ip_tgt, atualizar_ui=False)
                self.atribuir_ip_ao_slot(target_idx, ip_src, atualizar_ui=False)
                
                self.salvar_grid()
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
        ip_foco = self.grid_cameras[self.slot_maximized] if self.slot_maximized is not None else None
        for i, frm in enumerate(self.slot_frames):
            row, col = i // 5, i % 5
            frm.grid_configure(row=row, column=col, rowspan=1, columnspan=1, padx=1, pady=1, sticky="nsew")
            frm.configure(corner_radius=2)
            frm.grid()
            for child in frm.winfo_children(): child.pack_configure(padx=2, pady=2)
        self.slot_maximized = None
        if ip_foco: self.trocar_qualidade(ip_foco, 102)
        self.btn_expandir.lift()

    def selecionar_slot(self, index):
        if not (0 <= index < 20): return
        for frm in self.slot_frames: frm.configure(border_color="black", border_width=2)
        
        ip_anterior = self.ip_selecionado
        self.slot_selecionado = index
        self.slot_frames[index].configure(border_color=self.ACCENT_RED, border_width=2)
        
        self.title(f"Monitoramento ABI - Espaço {index + 1} selecionado")
        self.entry_nome.pack_forget()
        self.container_info_topo.pack(side="left", padx=10, pady=2)
        self.btn_renomear.configure(text="Renomear")
        
        ip_novo = self.grid_cameras[index]
        if ip_novo and ip_novo != "0.0.0.0":
            if ip_anterior and ip_anterior != ip_novo: self.pintar_botao(ip_anterior, "transparent")
            self.ip_selecionado = ip_novo
            nome = self.dados_cameras.get(ip_novo, "")
            self.entry_nome.delete(0, "end")
            self.entry_nome.insert(0, nome)
            self.pintar_botao(ip_novo, self.ACCENT_WINE)
            self.lbl_nome_topo.configure(text=self.formatar_nome(nome if nome else 'Câmera'))
            self.lbl_ip_topo.configure(text=f"({ip_novo})")
            self.btn_renomear.configure(state="normal")
            txt = "Diminuir" if self.slot_maximized == index else "Aumentar"
            self.btn_expandir.configure(text=txt)
            self.btn_expandir.place(in_=self.slot_frames[index], relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")
            self.btn_expandir.lift()
        else:
            if ip_anterior: self.pintar_botao(ip_anterior, "transparent")
            self.ip_selecionado = None
            self.entry_nome.delete(0, "end")
            self.lbl_nome_topo.configure(text="Nenhuma câmera selecionada")
            self.lbl_ip_topo.configure(text="")
            self.btn_renomear.configure(state="disabled")
            self.btn_expandir.place_forget()
        self.atualizar_botoes_controle()

    def limpar_slot_atual(self):
        self.press_data = None
        idx = self.slot_selecionado
        self.atribuir_ip_ao_slot(idx, "0.0.0.0")

        # Limpa preset ao remover manualmente
        if self.ultimo_preset:
            self.pintar_preset(self.ultimo_preset, self.BG_SIDEBAR)
            self.ultimo_preset = None

        if self.ip_selecionado:
            self.pintar_botao(self.ip_selecionado, "transparent")
            self.ip_selecionado = None
            self.entry_nome.delete(0, "end")
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

    def atribuir_ip_ao_slot(self, idx, ip, atualizar_ui=True, gerenciar_conexoes=True):
        if not (0 <= idx < 20): return
        
        # Limpa preset ao atribuir manualmente (se for uma atribuição direta, não via aplicar_preset)
        # Note: 'aplicar_preset' chama atribuir_ip_ao_slot com gerenciar_conexoes=False
        if gerenciar_conexoes and self.ultimo_preset:
            self.pintar_preset(self.ultimo_preset, self.BG_SIDEBAR)
            self.ultimo_preset = None

        ip_antigo = self.grid_cameras[idx]
        self.grid_cameras[idx] = ip
        
        # 1. Limpeza visual ultra-robusta
        txt = f"Espaço {idx+1}" if (not ip or ip == "0.0.0.0") else f"CONECTANDO...\n{ip}"

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
                self.iniciar_conexao_assincrona(ip, 102)

    def selecionar_camera(self, ip):
        # Esta função é chamada ao clicar na lista lateral
        if self.slot_selecionado is not None:
            self.atribuir_ip_ao_slot(self.slot_selecionado, ip)
            self.selecionar_slot(self.slot_selecionado)

    def pintar_botao(self, ip, cor):
        if ip and ip in self.botoes_referencia: self.botoes_referencia[ip]['frame'].configure(fg_color=cor)

    def pintar_preset(self, nome, cor):
        if nome and nome in self.preset_widgets:
            self.preset_widgets[nome].configure(fg_color=cor)

    def trocar_qualidade(self, ip, novo_canal):
        if not ip: return
        handler = self.camera_handlers.get(ip)
        if handler and handler != "CONECTANDO":
            if getattr(handler, 'canal', 101) != novo_canal:
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
            # RTSP String Padrão Hikvision/Intelbras
            url = f"rtsp://admin:1357gov%40@{ip}:554/Streaming/Channels/{canal}"
            nova_cam = CameraHandler(url, canal)
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

            # Mapeia quais IPs estão sendo processados para compartilhar a CTkImage se possível
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
                            if self.slot_labels[i].image != self.img_vazia:
                                self.slot_labels[i].configure(image=self.img_vazia, text=f"FALHA CONEXÃO\n{ip}")
                                self.slot_labels[i].image = self.img_vazia
                                self.slot_ctk_images[i] = None
                        except: pass
                        continue

                handler = self.camera_handlers.get(ip)
                if handler is None:
                    self.iniciar_conexao_assincrona(ip, 102)
                    continue
                if handler == "CONECTANDO":
                    continue

                try:
                    # Calcula tamanhos físicos
                    wf = self.slot_frames[i].winfo_width()
                    hf = self.slot_frames[i].winfo_height()
                    wf = int(max(10, wf - 6))
                    hf = int(max(10, hf - 6))

                    handler.tamanho_alvo = (wf, hf)
                    handler.interpolation = cv2.INTER_LINEAR if self.slot_maximized == i else cv2.INTER_NEAREST

                    pil_img = handler.pegar_frame()
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

        except Exception as e: print(f"Erro no loop de exibição: {e}")
        finally: self.after(40, self.loop_exibicao)

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
        if self.btn_renomear.cget("text") == "Renomear":
            self.container_info_topo.pack_forget()
            self.entry_nome.pack(side="left", padx=10, pady=5, before=self.btn_renomear)
            self.entry_nome.delete(0, "end")
            self.entry_nome.insert(0, self.dados_cameras.get(self.ip_selecionado, ""))
            self.btn_renomear.configure(text="Salvar")
        else:
            self.salvar_nome()
            self.entry_nome.pack_forget()
            self.container_info_topo.pack(side="left", padx=10, pady=2)
            self.btn_renomear.configure(text="Renomear")

    def salvar_nome(self):
        if self.ip_selecionado:
            novo_nome = self.entry_nome.get()
            self.dados_cameras[self.ip_selecionado] = novo_nome
            with open(self.arquivo_config, "w", encoding='utf-8') as f:
                json.dump(self.dados_cameras, f, ensure_ascii=False, indent=4)
            self.botoes_referencia[self.ip_selecionado]['lbl_nome'].configure(text=novo_nome)
            self.lbl_nome_topo.configure(text=self.formatar_nome(novo_nome))
            self.lbl_ip_topo.configure(text=f"({self.ip_selecionado})")
            self.filtrar_lista()

    def gerar_lista_ips(self):
        base = ["192.168.7.2", "192.168.7.3", "192.168.7.4", "192.168.7.20", "192.168.7.21",
                "192.168.7.22", "192.168.7.23", "192.168.7.24", "192.168.7.26", "192.168.7.27",
                "192.168.7.31", "192.168.7.32", "192.168.7.78", "192.168.7.79", "192.168.7.81",
                "192.168.7.89", "192.168.7.92", "192.168.7.94", "192.168.7.98", "192.168.7.99"]
        base += [f"192.168.7.{i}" for i in range(100, 216)]
        base += ["192.168.7.247", "192.168.7.248", "192.168.7.250", "192.168.7.251", "192.168.7.252"]
        return sorted(list(set(base)), key=lambda x: [int(d) for d in x.split('.')])

    def carregar_config(self):
        if os.path.exists(self.arquivo_config):
            try:
                with open(self.arquivo_config, "r", encoding='utf-8') as f: return json.load(f)
            except: pass
        return {}

    def obter_ips_ordenados(self):
        def chave_ordenacao(ip): return self.dados_cameras.get(ip, f"IP {ip}").lower()
        return sorted(self.ips_unicos, key=chave_ordenacao)

    def criar_botoes_iniciais(self):
        for ip in self.obter_ips_ordenados():
            nome = self.dados_cameras.get(ip, f"IP {ip}")
            frm = ctk.CTkFrame(self.scroll_frame, height=50, fg_color="transparent", border_width=1, border_color=self.GRAY_DARK)
            frm.pack(fill="x", pady=2); frm.pack_propagate(False)
            lbl_nome = ctk.CTkLabel(frm, text=nome, font=("Roboto", 13, "bold"), text_color=self.TEXT_P, anchor="w")
            lbl_nome.pack(fill="x", padx=10, pady=(4, 0))
            lbl_ip = ctk.CTkLabel(frm, text=ip, font=("Roboto", 11), text_color=self.TEXT_S, anchor="w")
            lbl_ip.pack(fill="x", padx=10, pady=(0, 4))
            for widget in [frm, lbl_nome, lbl_ip]:
                # O bind com lambda x=ip é seguro aqui
                widget.bind("<Button-1>", lambda e, x=ip: self.selecionar_camera(x))
                widget.configure(cursor="hand2")
            self.botoes_referencia[ip] = {'frame': frm, 'lbl_nome': lbl_nome, 'lbl_ip': lbl_ip}

    # --- MÉTODOS DE PRESETS ---
    def carregar_presets(self):
        if os.path.exists(self.arquivo_presets):
            try:
                with open(self.arquivo_presets, "r", encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {}

    def salvar_presets(self):
        try:
            with open(self.arquivo_presets, "w", encoding='utf-8') as f:
                json.dump(self.presets, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao salvar presets: {e}")

    def salvar_preset_atual(self):
        nome = simpledialog.askstring("Salvar Preset", "Digite um nome para esta predefinição:")
        if nome:
            if nome in self.presets:
                if not messagebox.askyesno("Confirmar", f"O preset '{nome}' já existe. Deseja sobrescrevê-lo?"):
                    return
            self.presets[nome] = list(self.grid_cameras)
            self.salvar_presets()
            self.atualizar_lista_presets_ui()
            # messagebox.showinfo("Presets", f"Predefinição '{nome}' salva com sucesso!")

    def aplicar_preset(self, nome):
        preset = self.presets.get(nome)
        if not preset: return

        # Limpa o cooldown para permitir reconexão imediata se for um preset
        self.cooldown_conexoes.clear()

        # Gerencia cores na lista de presets
        if self.ultimo_preset:
            self.pintar_preset(self.ultimo_preset, self.BG_SIDEBAR)
        self.ultimo_preset = nome
        self.pintar_preset(nome, self.ACCENT_WINE)

        # print(f"Aplicando predefinição: {nome}")

        # 1. Mapeia IPs atuais para saber o que fechar depois
        ips_antigos = set(ip for ip in self.grid_cameras if ip and ip != "0.0.0.0")

        # 2. Atualiza os dados do grid primeiro (silenciosamente)
        novos_ips = ["0.0.0.0"] * 20
        for i in range(20):
            ip = preset[i] if i < len(preset) else "0.0.0.0"
            novos_ips[i] = ip
            
            # Atualiza visualmente cada slot de forma segura
            self.atribuir_ip_ao_slot(i, ip, atualizar_ui=False, gerenciar_conexoes=False)

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

    def deletar_preset(self, nome):
        if messagebox.askyesno("Confirmar", f"Deseja realmente excluir o preset '{nome}'?"):
            if nome in self.presets:
                del self.presets[nome]
                self.salvar_presets()
                self.atualizar_lista_presets_ui()

    def renomear_preset(self, nome_antigo):
        novo_nome = simpledialog.askstring("Renomear Preset", f"Novo nome para '{nome_antigo}':", initialvalue=nome_antigo)
        if novo_nome and novo_nome != nome_antigo:
            if novo_nome in self.presets:
                messagebox.showerror("Erro", "Já existe um preset com este nome.")
                return
            self.presets[novo_nome] = self.presets.pop(nome_antigo)
            self.salvar_presets()
            self.atualizar_lista_presets_ui()

    def atualizar_lista_presets_ui(self):
        for child in self.scroll_presets.winfo_children():
            child.destroy()
        self.preset_widgets = {}

        for nome in sorted(self.presets.keys()):
            cor = self.ACCENT_WINE if nome == self.ultimo_preset else self.BG_SIDEBAR
            frm = ctk.CTkFrame(self.scroll_presets, height=50, fg_color=cor, border_width=1, border_color=self.GRAY_DARK)
            frm.pack(fill="x", pady=2, padx=2)
            frm.pack_propagate(False)
            
            # Label
            lbl = ctk.CTkLabel(frm, text=nome, font=("Roboto", 13, "bold"), text_color=self.TEXT_P, anchor="w", cursor="hand2")
            lbl.pack(side="left", fill="x", padx=10)
            
            # Bind no Frame E no Label para facilitar o clique
            frm.bind("<Button-1>", lambda e, n=nome: self.aplicar_preset(n))
            lbl.bind("<Button-1>", lambda e, n=nome: self.aplicar_preset(n))
            frm.configure(cursor="hand2")
            
            btn_ren = ctk.CTkButton(frm, text="R", width=30, height=30, fg_color=self.GRAY_DARK,
                                     hover_color=self.TEXT_S, command=lambda n=nome: self.renomear_preset(n))
            btn_ren.pack(side="right", padx=2)
            btn_del = ctk.CTkButton(frm, text="X", width=30, height=30, fg_color=self.ACCENT_WINE,
                                     hover_color=self.ACCENT_RED, command=lambda n=nome: self.deletar_preset(n))
            btn_del.pack(side="right", padx=5)

            self.preset_widgets[nome] = frm

if __name__ == "__main__":
    app = CentralMonitoramento()
    app.mainloop()
