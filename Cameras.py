import cv2
import customtkinter as ctk
from PIL import Image, ImageTk
import json
import os
import threading
import time
import socket
import queue
from tkinter import messagebox

# Configuração de baixa latência para OpenCV/FFMPEG
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp;analyzeduration;50000;probesize;50000;fflags;nobuffer;flags;low_delay;max_delay;0;bf;0"

# --- CLASSE DE VÍDEO OTIMIZADA ---
class CameraHandler:
    def __init__(self, url, canal=101):
        self.url = url
        self.canal = canal
        self.cap = None
        self.rodando = False
        self.frame_atual = None
        self.frame_novo = False
        self.lock = threading.Lock()
        self.conectado = False

    def iniciar(self):
        try:
            self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if self.cap.isOpened():
                self.rodando = True
                self.conectado = True
                threading.Thread(target=self.loop_leitura, daemon=True).start()
                return True
            else:
                return False
        except Exception as e:
            print(f"Erro driver: {e}")
            return False

    def loop_leitura(self):
        while self.rodando and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame_atual = frame
                    self.frame_novo = True
            else:
                time.sleep(0.01) # Reduzido para maior fluidez

        if self.cap:
            self.cap.release()

    def pegar_frame(self):
        with self.lock:
            if self.frame_novo:
                self.frame_novo = False
                return self.frame_atual
            return None

    def parar(self):
        self.rodando = False
        self.conectado = False

# --- INTERFACE PRINCIPAL ---
class CentralMonitoramento(ctk.CTk):
    # Cores do tema moderno
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

        self.title("Sistema de Monitoramento ABI - Full Control V4")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")

        self.bind("<Escape>", lambda event: self.sair_tela_cheia())

        # Configurações
        self.arquivo_config = os.path.join(os.path.expanduser("~"), "config_cameras_abi.json")
        self.ips_unicos = self.gerar_lista_ips()
        self.dados_cameras = self.carregar_config()
        self.botoes_referencia = {}

        self.ip_selecionado = None
        self.camera_handlers = {}
        self.em_tela_cheia = False
        self.slot_maximized = None
        self.arquivo_grid = os.path.join(os.path.expanduser("~"), "grid_config_abi.json")
        self.grid_cameras = self.carregar_grid()
        self.slot_selecionado = 0
        self.press_data = None
        self.fila_conexoes = queue.Queue()
        self.cooldown_conexoes = {}

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. BARRA LATERAL
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=self.BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(self.sidebar, text="CÂMERAS", font=("Roboto", 20, "bold"), text_color=self.ACCENT_RED).pack(pady=(15, 5))

        # Busca
        self.frame_busca = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_busca.pack(fill="x", padx=10, pady=5)

        self.entry_busca = ctk.CTkEntry(self.frame_busca, placeholder_text="Filtrar...")
        self.entry_busca.pack(fill="x", expand=True)
        self.entry_busca.bind("<KeyRelease>", lambda e: self.filtrar_lista())

        self.scroll_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.scroll_frame.pack(expand=True, fill="both", padx=5, pady=5)

        # 2. ÁREA PRINCIPAL (Direita)
        self.main_frame = ctk.CTkFrame(self, fg_color=self.BG_MAIN, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")

        # Topo
        self.painel_topo = ctk.CTkFrame(self.main_frame, fg_color=self.BG_PANEL, height=50)
        self.painel_topo.pack(side="top", fill="x", padx=10, pady=10)

        # Info da câmera (alinhada à esquerda)
        self.container_info_topo = ctk.CTkFrame(self.painel_topo, fg_color="transparent")
        self.container_info_topo.pack(side="left", padx=10, pady=5)

        self.lbl_nome_topo = ctk.CTkLabel(self.container_info_topo, text="Nenhuma câmera selecionada",
                                          font=("Roboto", 15, "bold"), text_color=self.ACCENT_RED)
        self.lbl_nome_topo.pack(side="left")

        self.lbl_ip_topo = ctk.CTkLabel(self.container_info_topo, text="",
                                        font=("Roboto", 13), text_color=self.TEXT_S)
        self.lbl_ip_topo.pack(side="left", padx=(5, 0))

        # Botões do topo (alinhados à direita)
        self.btn_fullscreen = ctk.CTkButton(self.painel_topo, text="Tela Cheia [ESC]", command=self.entrar_tela_cheia,
                                            fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED, width=120)
        self.btn_fullscreen.pack(side="right", padx=5)

        self.btn_limpar_slot = ctk.CTkButton(self.painel_topo, text="Limpar", command=self.limpar_slot_atual,
                                             fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE, width=120)
        self.btn_limpar_slot.pack(side="right", padx=5)

        self.btn_renomear = ctk.CTkButton(self.painel_topo, text="Renomear", command=self.alternar_edicao_nome,
                                        fg_color=self.GRAY_DARK, hover_color=self.TEXT_S, width=100, state="disabled")
        self.btn_renomear.pack(side="right", padx=5)

        self.entry_nome = ctk.CTkEntry(self.painel_topo, width=300, placeholder_text="Nome da câmera...")
        # Pack gerenciado pelo botão renomear

        # Rodapé
        self.painel_base = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.painel_base.pack(side="bottom", fill="x", padx=10, pady=10)

        self.btn_toggle_grid = ctk.CTkButton(self.painel_base, text="1 camera", fg_color=self.ACCENT_WINE,
                                             hover_color=self.ACCENT_RED, height=40, command=self.toggle_grid_layout)
        self.btn_toggle_grid.pack(side="left", expand=True, fill="x", padx=5)

        # Grid de Câmeras
        self.grid_frame = ctk.CTkFrame(self.main_frame, fg_color="#000000")
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 10))

        for i in range(4): self.grid_frame.grid_rowconfigure(i, weight=1)
        for i in range(5): self.grid_frame.grid_columnconfigure(i, weight=1)

        self.slot_frames = []
        self.slot_labels = []
        for i in range(20):
            row, col = i // 5, i % 5
            
            # Frame com borda preta
            frm = ctk.CTkFrame(self.grid_frame, fg_color=self.BG_SIDEBAR, corner_radius=2, border_width=2, border_color="black")
            
            frm.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            frm.pack_propagate(False)

            lbl = ctk.CTkLabel(frm, text=f"Espaço {i+1}", corner_radius=0)
            
            # Label com padding para não cobrir a borda
            lbl.pack(expand=True, fill="both", padx=2, pady=2)

            # Bindings
            frm.bind("<Button-1>", lambda e, idx=i: self.ao_pressionar_slot(e, idx))
            lbl.bind("<Button-1>", lambda e, idx=i: self.ao_pressionar_slot(e, idx))
            frm.bind("<ButtonRelease-1>", lambda e, idx=i: self.ao_soltar_slot(e, idx))
            lbl.bind("<ButtonRelease-1>", lambda e, idx=i: self.ao_soltar_slot(e, idx))

            self.slot_frames.append(frm)
            self.slot_labels.append(lbl)

        self.criar_botoes_iniciais()

        for i, ip in enumerate(self.grid_cameras):
            if ip and ip != "0.0.0.0": self.slot_labels[i].configure(text=f"CARREGANDO\n{ip}")

        self.selecionar_slot(0)
        self.restaurar_grid()
        self.alternar_todos_streams()
        self.loop_exibicao()

    # --- LÓGICA DO GRID ---
    def maximizar_slot(self, index):
        self.grid_frame.pack_configure(padx=0, pady=0)
        for i, frm in enumerate(self.slot_frames):
            if i == index:
                frm.grid_configure(row=0, column=0, rowspan=4, columnspan=5, padx=0, pady=0, sticky="nsew")
                frm.configure(corner_radius=0)
                for child in frm.winfo_children():
                    child.pack_configure(padx=0, pady=0)
            else:
                frm.grid_forget()
        self.slot_maximized = index

        ip = self.grid_cameras[index]
        if ip: self.trocar_qualidade(ip, 101)

    def ao_pressionar_slot(self, event, index):
        self.selecionar_slot(index)
        self.press_data = {"index": index, "x": event.x_root, "y": event.y_root}

    def ao_soltar_slot(self, event, index):
        if not self.press_data: return
        source_idx = self.press_data.get("index")

        # Se estiver em tela cheia ou slot maximizado, desativa drag-and-drop
        if self.slot_maximized is not None or self.em_tela_cheia:
            self.press_data = None
            return

        try:
            dist = ((event.x_root - self.press_data["x"])**2 + (event.y_root - self.press_data["y"])**2)**0.5
            target_idx = self.encontrar_slot_por_coords(event.x_root, event.y_root)

            # Se for apenas um clique ou soltou fora de qualquer slot
            if dist < 15 or target_idx is None:
                final_idx = target_idx if target_idx is not None else source_idx
                if 0 <= final_idx < 20:
                    self.selecionar_slot(final_idx)
                return

            # Se soltou no mesmo slot de origem, apenas seleciona
            if target_idx == source_idx:
                self.selecionar_slot(source_idx)
                return

            # Validação de troca entre slots
            if 0 <= source_idx < 20 and 0 <= target_idx < 20:
                # Se o de origem for vazio, não permite arrastar
                if self.grid_cameras[source_idx] == "0.0.0.0":
                    self.selecionar_slot(target_idx)
                    return

                # Realiza a troca lógica apenas na lista de IPs
                self.grid_cameras[source_idx], self.grid_cameras[target_idx] = \
                    self.grid_cameras[target_idx], self.grid_cameras[source_idx]

                # Limpa visualmente o slot de origem se ele ficou vazio para evitar "fantasma"
                for idx in [source_idx, target_idx]:
                    if self.grid_cameras[idx] == "0.0.0.0":
                        try: self.slot_labels[idx].configure(image="", text=f"Espaço {idx+1}")
                        except: pass
                        self.slot_labels[idx].image = None

                self.salvar_grid()
                self.selecionar_slot(target_idx)
        finally:
            self.press_data = None

    def encontrar_slot_por_coords(self, x_root, y_root):
        for i, frm in enumerate(self.slot_frames):
            if not frm.winfo_viewable(): continue
            fx, fy = frm.winfo_rootx(), frm.winfo_rooty()
            fw, fh = frm.winfo_width(), frm.winfo_height()
            if fx <= x_root <= fx + fw and fy <= y_root <= fy + fh:
                return i
        return None

    def restaurar_grid(self):
        self.grid_frame.pack_configure(padx=10, pady=(0, 10))
        ip_foco = self.grid_cameras[self.slot_maximized] if self.slot_maximized is not None else None

        for i, frm in enumerate(self.slot_frames):
            row, col = i // 5, i % 5
            frm.grid_configure(row=row, column=col, rowspan=1, columnspan=1, padx=1, pady=1, sticky="nsew")
            frm.configure(corner_radius=2)
            frm.grid()
            for child in frm.winfo_children():
                child.pack_configure(padx=2, pady=2)
                
        self.slot_maximized = None
        if ip_foco: self.trocar_qualidade(ip_foco, 102)

    def selecionar_slot(self, index):
        if not (0 <= index < 20): return
        # Desmarca todos para garantir que não haja fantasmas de seleção
        for frm in self.slot_frames:
            frm.configure(border_color="black", border_width=2)

        ip_anterior = self.ip_selecionado
        self.slot_selecionado = index
        
        self.slot_frames[index].configure(border_color=self.ACCENT_RED, border_width=2)
        self.title(f"Monitoramento ABI - Espaço {index + 1} selecionado")

        # Reset modo edição se estiver ativo
        self.entry_nome.pack_forget()
        self.container_info_topo.pack(side="left", padx=10, pady=5)
        self.btn_renomear.configure(text="Renomear")

        ip_novo = self.grid_cameras[index]
        if ip_novo and ip_novo != "0.0.0.0":
            if ip_anterior and ip_anterior != ip_novo:
                self.pintar_botao(ip_anterior, "transparent")
            self.ip_selecionado = ip_novo
            nome = self.dados_cameras.get(ip_novo, "")
            self.entry_nome.delete(0, "end")
            self.entry_nome.insert(0, nome)
            self.pintar_botao(ip_novo, self.ACCENT_WINE)

            self.lbl_nome_topo.configure(text=self.formatar_nome(nome if nome else 'Câmera'))
            self.lbl_ip_topo.configure(text=f"({ip_novo})")
            self.btn_renomear.configure(state="normal")
        else:
            if ip_anterior: self.pintar_botao(ip_anterior, "transparent")
            self.ip_selecionado = None
            self.entry_nome.delete(0, "end")

            self.lbl_nome_topo.configure(text="Nenhuma câmera selecionada")
            self.lbl_ip_topo.configure(text="")
            self.btn_renomear.configure(state="disabled")

        self.atualizar_botoes_controle()

    def limpar_slot_atual(self):
        self.press_data = None
        idx = self.slot_selecionado
        self.atribuir_ip_ao_slot(idx, "0.0.0.0")
        
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
            self.btn_toggle_grid.configure(text="Minimizar camera", fg_color=self.GRAY_DARK, hover_color=self.TEXT_S)
        else:
            self.btn_toggle_grid.configure(text="Expandir camera", fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED)

    def toggle_grid_layout(self):
        if self.slot_maximized is not None:
            self.restaurar_grid()
        else:
            self.maximizar_slot(self.slot_selecionado)
        self.atualizar_botoes_controle()

    def atribuir_ip_ao_slot(self, idx, ip):
        if not (0 <= idx < 20): return
        
        ip_antigo = self.grid_cameras[idx]
        self.grid_cameras[idx] = ip

        # Reset visual robusto
        try: self.slot_labels[idx].configure(image="")
        except: pass

        try:
            if ip == "0.0.0.0":
                self.slot_labels[idx].configure(text=f"Espaço {idx+1}")
            else:
                self.slot_labels[idx].configure(text=f"CONECTANDO\n{ip}")
        except: pass
        
        self.slot_labels[idx].image = None
        self.update_idletasks()
        self.salvar_grid()

        # Limpeza de handler antigo se não for mais usado no grid
        if ip_antigo and ip_antigo != "0.0.0.0" and ip_antigo != ip and ip_antigo not in self.grid_cameras:
            if ip_antigo in self.camera_handlers:
                try: self.camera_handlers[ip_antigo].parar()
                except: pass
                del self.camera_handlers[ip_antigo]

        # Inicia nova conexão
        if ip != "0.0.0.0":
            if ip in self.cooldown_conexoes: del self.cooldown_conexoes[ip]
            self.iniciar_conexao_assincrona(ip, 102)

    def selecionar_camera(self, ip):
        if self.slot_selecionado is not None:
            self.atribuir_ip_ao_slot(self.slot_selecionado, ip)
            self.selecionar_slot(self.slot_selecionado)

    def pintar_botao(self, ip, cor):
        if ip and ip in self.botoes_referencia:
            self.botoes_referencia[ip]['frame'].configure(fg_color=cor)

    def entrar_tela_cheia(self):
        if self.em_tela_cheia: return
        self.em_tela_cheia = True
        self.attributes("-fullscreen", True)
        self.sidebar.grid_forget()
        self.main_frame.grid_configure(column=0, columnspan=2)
        self.painel_topo.pack_forget()
        self.painel_base.pack_forget()
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

    def sair_tela_cheia(self):
        if not self.em_tela_cheia: return
        self.em_tela_cheia = False
        self.attributes("-fullscreen", False)
        if hasattr(self, 'btn_sair_fs'): self.btn_sair_fs.destroy()

        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_configure(column=1, columnspan=1)
        
        indices_visiveis = [self.slot_maximized] if self.slot_maximized is not None else range(len(self.slot_frames))
        for i, frm in enumerate(self.slot_frames):
            if i in indices_visiveis:
                frm.grid_configure(padx=1, pady=1, sticky="nsew")
                frm.configure(corner_radius=2)
                for child in frm.winfo_children():
                    child.pack_configure(padx=2, pady=2)
            else:
                frm.grid_forget()

        self.painel_topo.pack_forget()
        self.painel_base.pack_forget()
        self.grid_frame.pack_forget()
        self.painel_topo.pack(side="top", fill="x", padx=10, pady=10)
        self.painel_base.pack(side="bottom", fill="x", padx=10, pady=10)

        # Ajusta padding do grid_frame: 0 se estiver maximizado, padrão se não estiver
        padx_grid = 0 if self.slot_maximized is not None else 10
        pady_grid = 0 if self.slot_maximized is not None else (0, 10)
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=padx_grid, pady=pady_grid)

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
        if len(nome) > max_chars:
            return nome[:max_chars-3] + "..."
        return nome

    def iniciar_conexao_assincrona(self, ip, canal=102):
        if not ip or ip == "0.0.0.0": return
        
        # Cooldown para evitar spam em caso de falha (10 segundos)
        agora = time.time()
        if ip in self.cooldown_conexoes:
            if agora - self.cooldown_conexoes[ip] < 10:
                return

        # Proteção: Se já existe handler, evita múltiplas tentativas simultâneas
        if ip in self.camera_handlers:
            handler = self.camera_handlers[ip]
            if handler == "CONECTANDO": return
            if hasattr(handler, 'rodando') and handler.rodando:
                return # Já está rodando OK

            # Se está "morto" ou travado, remove para reconectar
            del self.camera_handlers[ip]

        self.camera_handlers[ip] = "CONECTANDO"
        threading.Thread(target=self._thread_conectar, args=(ip, canal), daemon=True).start()

    def _thread_conectar(self, ip, canal):
        try:
            url = f"rtsp://admin:1357gov%40@{ip}:554/Streaming/Channels/{canal}"
            nova_cam = CameraHandler(url, canal)
            sucesso = nova_cam.iniciar()
            self.fila_conexoes.put((sucesso, nova_cam, ip))
        except Exception as e:
            print(f"Erro crítico na thread de conexão ({ip}): {e}")
            self.fila_conexoes.put((False, None, ip))

    def _pos_conexao(self, sucesso, camera_obj, ip):
        if sucesso:
            self.camera_handlers[ip] = camera_obj
            if ip in self.cooldown_conexoes: del self.cooldown_conexoes[ip]
        else:
            if ip in self.camera_handlers: del self.camera_handlers[ip]
            self.cooldown_conexoes[ip] = time.time()
            # Informa o erro visualmente em todos os slots que usam este IP
            for i, grid_ip in enumerate(self.grid_cameras):
                if grid_ip == ip:
                    try: self.slot_labels[i].configure(text=f"ERRO AO CONECTAR\n{ip}")
                    except: pass
        self.atualizar_botoes_controle()

    def loop_exibicao(self):
        try:
            # Processar resultados de conexões em background
            while not self.fila_conexoes.empty():
                try:
                    sucesso, camera_obj, ip = self.fila_conexoes.get_nowait()
                    self._pos_conexao(sucesso, camera_obj, ip)
                except: pass

            agora = time.time()
            indices = [self.slot_maximized] if self.slot_maximized is not None else range(20)
            frames_cache = {}

            for i in indices:
                ip = self.grid_cameras[i]
                if not ip or ip == "0.0.0.0": continue

                # Feedback visual de cooldown
                if ip in self.cooldown_conexoes:
                    if agora - self.cooldown_conexoes[ip] < 10:
                        try: self.slot_labels[i].configure(text=f"ERRO AO CONECTAR\n{ip}")
                        except: pass
                        continue

                if ip not in frames_cache:
                    handler = self.camera_handlers.get(ip)
                    if handler is None:
                        self.iniciar_conexao_assincrona(ip, 102)
                        frames_cache[ip] = None
                        continue
                    if handler == "CONECTANDO":
                        frames_cache[ip] = None
                        continue
                    frames_cache[ip] = handler.pegar_frame()

                frame = frames_cache[ip]
                if frame is not None:
                    try:
                        w = self.slot_frames[i].winfo_width()
                        h = self.slot_frames[i].winfo_height()
                        w = max(10, w - 6)
                        h = max(10, h - 6)

                        frame_resized = cv2.resize(frame, (w, h), interpolation=cv2.INTER_NEAREST)

                        pos = (10, h - 10)
                        cv2.putText(frame_resized, ip, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
                        cv2.putText(frame_resized, ip, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

                        pil_img = Image.fromarray(cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB))
                        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w, h))

                        # Atualização final do label
                        try: self.slot_labels[i].configure(image=ctk_img, text="")
                        except: pass
                        self.slot_labels[i].image = ctk_img # Segura referência
                    except: pass
        except Exception as e:
            print(f"Erro no loop de exibição: {e}")
        finally:
            self.after(40, self.loop_exibicao)

    def filtrar_lista(self):
        termo = self.entry_busca.get().lower()

        # Primeiro, remove todos do pack para garantir que a ordem seja reiniciada
        for item in self.botoes_referencia.values():
            item['frame'].pack_forget()

        # Garante que os itens sejam exibidos na ordem alfabética atualizada
        for ip in self.obter_ips_ordenados():
            item = self.botoes_referencia.get(ip)
            if not item: continue

            nome = self.dados_cameras.get(ip, "").lower()
            if termo in ip or termo in nome:
                item['frame'].pack(fill="x", pady=2)

        # Scroll para o topo ao filtrar
        try:
            if hasattr(self.scroll_frame, "_parent_canvas"):
                self.scroll_frame._parent_canvas.yview_moveto(0)
        except:
            pass

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
            self.container_info_topo.pack(side="left", padx=10, pady=5)
            self.btn_renomear.configure(text="Renomear")

    def salvar_nome(self):
        if self.ip_selecionado:
            novo_nome = self.entry_nome.get()
            self.dados_cameras[self.ip_selecionado] = novo_nome
            with open(self.arquivo_config, "w", encoding='utf-8') as f:
                json.dump(self.dados_cameras, f, ensure_ascii=False, indent=4)

            # Atualiza labels e reordena a lista
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
        # Retorna a lista de IPs ordenados alfabeticamente pelo nome da câmera
        def chave_ordenacao(ip):
            nome = self.dados_cameras.get(ip, f"IP {ip}")
            return nome.lower()

        return sorted(self.ips_unicos, key=chave_ordenacao)

    def criar_botoes_iniciais(self):
        for ip in self.obter_ips_ordenados():
            nome = self.dados_cameras.get(ip, f"IP {ip}")

            # Frame container para simular o botão
            frm = ctk.CTkFrame(self.scroll_frame, height=50, fg_color="transparent", border_width=1, border_color=self.GRAY_DARK)
            frm.pack(fill="x", pady=2)
            frm.pack_propagate(False)

            # Labels internos com cores diferentes
            lbl_nome = ctk.CTkLabel(frm, text=nome, font=("Roboto", 13, "bold"), text_color=self.TEXT_P, anchor="w")
            lbl_nome.pack(fill="x", padx=10, pady=(4, 0))

            lbl_ip = ctk.CTkLabel(frm, text=ip, font=("Roboto", 11), text_color=self.TEXT_S, anchor="w")
            lbl_ip.pack(fill="x", padx=10, pady=(0, 4))

            # Bindings de clique para o frame e para as labels
            for widget in [frm, lbl_nome, lbl_ip]:
                widget.bind("<Button-1>", lambda e, x=ip: self.selecionar_camera(x))
                widget.configure(cursor="hand2")

            self.botoes_referencia[ip] = {
                'frame': frm,
                'lbl_nome': lbl_nome,
                'lbl_ip': lbl_ip
            }

if __name__ == "__main__":
    app = CentralMonitoramento()
    app.mainloop()
