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

# Configuração de baixa latência para OpenCV/FFMPEG - Trocado UDP por TCP para maior estabilidade
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp;analyzeduration;50000;probesize;50000;fflags;nobuffer;flags;low_delay;max_delay;0;bf;0"

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
        falhas_consecutivas = 0
        while self.rodando:
            if not self.cap or not self.cap.isOpened():
                self.conectado = False
                time.sleep(2)
                try:
                    self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if self.cap.isOpened():
                        self.conectado = True
                        falhas_consecutivas = 0
                    else:
                        continue
                except:
                    continue

            ret, frame = self.cap.read()
            if ret:
                falhas_consecutivas = 0
                self.conectado = True

                # Pre-processamento: Conversão de cor no thread da câmera (Otimização de Performance)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                with self.lock:
                    self.frame_atual = rgb_frame
                    self.frame_novo = True
            else:
                falhas_consecutivas += 1
                # Se falhar muitas vezes seguidas (aprox 2 segundos), tenta reabrir a captura
                if falhas_consecutivas > 100:
                    self.cap.release()
                    self.conectado = False
                    falhas_consecutivas = 0
                time.sleep(0.01)

        if self.cap:
            self.cap.release()
        self.rodando = False
        self.conectado = False

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

        self.title("Sistema de Monitoramento ABI - Full Control V5")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")
        
        # --- CONFIGURAÇÃO DE JANELA ---
        self.after(0, lambda: self.state("zoomed"))
        
        # Credenciais para PTZ
        self.user_ptz = "admin"
        self.pass_ptz = "1357gov@"

        self.protocol("WM_DELETE_WINDOW", self.ao_fechar)
        
        # Binds de Teclado
        self.bind("<Escape>", lambda event: self.sair_ou_minimizar())
        
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

        self.presets = self.carregar_presets()
        self.ips_unicos = self.gerar_lista_ips()
        self.dados_cameras = self.carregar_config()
        self.grid_cameras = self.carregar_grid()
        
        self.botoes_referencia = {}
        self.ip_selecionado = None
        self.camera_handlers = {}
        self.slot_maximized = None
        self.slot_selecionado = 0
        self.press_data = None
        self.fila_conexoes = queue.Queue()
        self.fila_pendente_conexoes = queue.Queue()
        self.cooldown_conexoes = {}
        self.tecla_pressionada = None 
        
        # Variável para guardar o botão de overlay (Aumentar/Diminuir)
        self.btn_overlay_cam = None
        
        # Controle de visibilidade dos menus (Começa oculto)
        self.menus_visiveis = False

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. SIDEBAR (Menu Lateral)
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=self.BG_SIDEBAR)
        # Inicialmente não faz grid, pois começa oculto
        
        # --- NOVO: Botão FECHAR MENU dentro da Sidebar (Não sobrepõe) ---
        self.btn_fechar_menu = ctk.CTkButton(self.sidebar, text="FECHAR MENU", 
                                             fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED,
                                             font=("Roboto", 12, "bold"), height=40,
                                             command=self.alternar_menu)
        self.btn_fechar_menu.pack(fill="x", padx=10, pady=(15, 5))

        self.tabview = ctk.CTkTabview(self.sidebar, fg_color="transparent",
                                      segmented_button_selected_color=self.ACCENT_RED,
                                      segmented_button_unselected_hover_color=self.ACCENT_WINE,
                                      text_color=self.TEXT_P)
        self.tabview.pack(expand=True, fill="both", padx=5, pady=5)
        self.tabview.add("Câmeras")
        self.tabview.add("Predefinições")

        # --- ABA CÂMERAS ---
        tab_cams = self.tabview.tab("Câmeras")
        self.frame_busca = ctk.CTkFrame(tab_cams, fg_color="transparent")
        self.frame_busca.pack(fill="x", padx=5, pady=5)

        self.entry_busca = ctk.CTkEntry(self.frame_busca, placeholder_text="Filtrar...")
        self.entry_busca.pack(fill="x", expand=True)
        self.entry_busca.bind("<KeyRelease>", lambda e: self.filtrar_lista())

        self.scroll_frame = ctk.CTkScrollableFrame(tab_cams, fg_color="transparent")
        self.scroll_frame.pack(expand=True, fill="both", padx=0, pady=5)

        # --- ABA PREDEFINIÇÕES ---
        tab_presets = self.tabview.tab("Predefinições")

        self.btn_salvar_preset = ctk.CTkButton(tab_presets, text="Salvar Preset Atual",
                                                fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED,
                                                command=self.salvar_preset_atual)
        self.btn_salvar_preset.pack(fill="x", padx=10, pady=10)

        # --- ALTERADO: DE "LISTA DE PRESETS" PARA "PREDEFINIÇÕES" ---
        ctk.CTkLabel(tab_presets, text="PREDEFINIÇÕES", font=("Roboto", 14, "bold"), text_color=self.TEXT_S).pack(pady=5)

        self.scroll_presets = ctk.CTkScrollableFrame(tab_presets, fg_color="transparent")
        self.scroll_presets.pack(expand=True, fill="both", padx=5, pady=5)

        # 2. ÁREA PRINCIPAL
        self.main_frame = ctk.CTkFrame(self, fg_color=self.BG_MAIN, corner_radius=0)
        self.main_frame.grid(row=0, column=0, columnspan=2, sticky="nsew") 

        # PAINEL TOPO
        self.painel_topo = ctk.CTkFrame(self.main_frame, fg_color=self.BG_PANEL, height=50)

        # INFO CÂMERA NO TOPO
        self.container_info_topo = ctk.CTkFrame(self.painel_topo, fg_color="transparent")
        self.container_info_topo.pack(side="left", padx=50, pady=5) 

        self.lbl_nome_topo = ctk.CTkLabel(self.container_info_topo, text="Nenhuma câmera selecionada",
                                          font=("Roboto", 15, "bold"), text_color=self.ACCENT_RED)
        self.lbl_nome_topo.pack(side="left")

        self.lbl_ip_topo = ctk.CTkLabel(self.container_info_topo, text="",
                                        font=("Roboto", 13), text_color=self.TEXT_S)
        self.lbl_ip_topo.pack(side="left", padx=(5, 0))

        # BOTÕES DIREITA TOPO
        self.btn_limpar_slot = ctk.CTkButton(self.painel_topo, text="Limpar", command=self.limpar_slot_atual,
                                             fg_color=self.ACCENT_RED, hover_color=self.ACCENT_WINE, width=120)
        self.btn_limpar_slot.pack(side="right", padx=5)

        self.btn_renomear = ctk.CTkButton(self.painel_topo, text="Renomear", command=self.alternar_edicao_nome,
                                        fg_color=self.GRAY_DARK, hover_color=self.TEXT_S, width=100, state="disabled")
        self.btn_renomear.pack(side="right", padx=5)

        self.entry_nome = ctk.CTkEntry(self.painel_topo, width=300, placeholder_text="Nome da câmera...")

        # PAINEL BASE
        self.painel_base = ctk.CTkFrame(self.main_frame, fg_color="transparent")

        self.lbl_ptz_hint = ctk.CTkLabel(self.painel_base, text="Use as setas do teclado para mover a câmera selecionada", 
                                         font=("Roboto", 11), text_color=self.TEXT_S)
        self.lbl_ptz_hint.pack(side="bottom")

        # Botão Toggle Grid no painel inferior (ainda existe, mas agora temos os botões overlay)
        self.btn_toggle_grid = ctk.CTkButton(self.painel_base, text="1 camera", fg_color=self.ACCENT_WINE,
                                             hover_color=self.ACCENT_RED, height=40, command=self.toggle_grid_layout)
        self.btn_toggle_grid.pack(side="left", expand=True, fill="x", padx=5)

        # GRID DE VÍDEO
        self.grid_frame = ctk.CTkFrame(self.main_frame, fg_color="#000000")
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=0, pady=0) 

        for i in range(4): self.grid_frame.grid_rowconfigure(i, weight=1)
        for i in range(5): self.grid_frame.grid_columnconfigure(i, weight=1)

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

        # --- BOTÃO MENU FLUTUANTE (ABRIR) ---
        # Este botão aparece apenas quando o menu lateral está fechado
        self.btn_abrir_menu = ctk.CTkButton(self, text="ABRIR MENU", width=120, height=40,
                                      fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED,
                                      font=("Roboto", 12, "bold"),
                                      command=self.alternar_menu)
        self.btn_abrir_menu.place(x=10, y=10) # FLUTUANTE

        self.criar_botoes_iniciais()
        for i, ip in enumerate(self.grid_cameras):
            if ip and ip != "0.0.0.0": self.slot_labels[i].configure(text=f"CARREGANDO\n{ip}")

        self.selecionar_slot(0)
        self.restaurar_grid()
        self.alternar_todos_streams()
        self.atualizar_lista_presets_ui()

        # Inicia worker para conexões escalonadas
        threading.Thread(target=self._processar_fila_conexoes_pendentes, daemon=True).start()

        self.loop_exibicao()

    # --- LÓGICA DO MENU EXPANSÍVEL ---
    def alternar_menu(self):
        if self.menus_visiveis:
            # OCULTAR MENUS (Modo Imersivo)
            self.sidebar.grid_remove()
            self.painel_topo.pack_forget()
            self.painel_base.pack_forget()
            
            # Expande o main_frame para a coluna 0
            self.main_frame.grid_configure(column=0, columnspan=2)
            
            # Remove paddings do grid de vídeo para aproveitar espaço total
            self.grid_frame.pack_configure(padx=0, pady=0)
            
            self.menus_visiveis = False
            
            # Mostra o botão flutuante de ABRIR
            self.btn_abrir_menu.place(x=10, y=10)
            self.btn_abrir_menu.lift()
        else:
            # MOSTRAR MENUS (Modo Controle)
            # Esconde o botão flutuante de ABRIR
            self.btn_abrir_menu.place_forget()

            self.sidebar.grid(row=0, column=0, sticky="nsew")
            
            # Restringe main_frame para coluna 1
            self.main_frame.grid_configure(column=1, columnspan=1)
            
            # Mostra painéis superior e inferior
            self.painel_topo.pack(side="top", fill="x", padx=10, pady=10, before=self.grid_frame)
            self.painel_base.pack(side="bottom", fill="x", padx=10, pady=10)
            
            # Adiciona paddings para estética
            self.grid_frame.pack_configure(padx=10, pady=(0, 10))
            
            self.menus_visiveis = True

    def sair_ou_minimizar(self):
        if messagebox.askyesno("Sair", "Deseja fechar o sistema?"):
            self.ao_fechar()

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

    # --- MÉTODOS UI ---
    def ao_fechar(self):
        self.destroy()
        os._exit(0)

    # --- FUNÇÃO ATUALIZADA PARA BOTÃO SOBREPOSTO NA CÂMERA ---
    def atualizar_botao_overlay(self, slot_index):
        # Remove botão anterior, se existir
        if self.btn_overlay_cam:
            try:
                self.btn_overlay_cam.destroy()
            except:
                pass
            self.btn_overlay_cam = None

        if slot_index is None:
            return

        # Define frame pai (o slot selecionado)
        parent_frame = self.slot_frames[slot_index]
        
        # Lógica do botão (Aumentar ou Diminuir)
        if self.slot_maximized == slot_index:
            texto = "Diminuir"
            cmd = self.toggle_grid_layout
            # AGORA USA COR DE DESTAQUE (Vermelho/Vinho)
            cor = self.ACCENT_WINE
            hover = self.ACCENT_RED
            # DOBRO DO TAMANHO (Width 70 -> 140, Height 24 -> 48)
            w_btn = 140 
            h_btn = 48
            font_size = 14 # Fonte levemente maior
        else:
            texto = "Aumentar"
            cmd = lambda: self.maximizar_slot(slot_index)
            cor = self.ACCENT_WINE
            hover = self.ACCENT_RED
            w_btn = 70
            h_btn = 24
            font_size = 11

        # Cria o botão dentro do frame do slot
        self.btn_overlay_cam = ctk.CTkButton(parent_frame, text=texto, width=w_btn, height=h_btn,
                                             fg_color=cor, hover_color=hover,
                                             font=("Roboto", font_size, "bold"),
                                             bg_color="transparent",
                                             command=cmd)
        
        # --- POSICIONAMENTO NO CANTO INFERIOR DIREITO ---
        # relx=1.0, rely=1.0 define o ponto de referência no canto inferior direito do frame pai
        # anchor="se" (South East) faz com que o botão cresça para a esquerda e para cima a partir desse ponto
        self.btn_overlay_cam.place(relx=1.0, rely=1.0, x=-5, y=-5, anchor="se")
        self.btn_overlay_cam.lift() # Traz para frente

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
        
        # Atualiza o botão overlay para "Diminuir"
        self.atualizar_botao_overlay(index)

    def ao_pressionar_slot(self, event, index):
        self.selecionar_slot(index)
        self.press_data = {"index": index, "x": event.x_root, "y": event.y_root}

    def ao_soltar_slot(self, event, index):
        if not self.press_data: return
        source_idx = self.press_data.get("index")
        if self.slot_maximized is not None:
            self.press_data = None
            return
        try:
            dist = ((event.x_root - self.press_data["x"])**2 + (event.y_root - self.press_data["y"])**2)**0.5
            target_idx = self.encontrar_slot_por_coords(event.x_root, event.y_root)
            if dist < 15 or target_idx is None:
                final_idx = target_idx if target_idx is not None else source_idx
                if 0 <= final_idx < 20: self.selecionar_slot(final_idx)
                return
            if target_idx == source_idx:
                self.selecionar_slot(source_idx)
                return
            if 0 <= source_idx < 20 and 0 <= target_idx < 20:
                if self.grid_cameras[source_idx] == "0.0.0.0":
                    self.selecionar_slot(target_idx)
                    return
                self.grid_cameras[source_idx], self.grid_cameras[target_idx] = \
                    self.grid_cameras[target_idx], self.grid_cameras[source_idx]
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
            if fx <= x_root <= fx + fw and fy <= y_root <= fy + fh: return i
        return None

    def restaurar_grid(self):
        # Se os menus estiverem visíveis, restaura com padding
        pady = (0, 10) if self.menus_visiveis else 0
        padx = 10 if self.menus_visiveis else 0
        self.grid_frame.pack_configure(padx=padx, pady=pady)
        
        ip_foco = self.grid_cameras[self.slot_maximized] if self.slot_maximized is not None else None
        for i, frm in enumerate(self.slot_frames):
            row, col = i // 5, i % 5
            frm.grid_configure(row=row, column=col, rowspan=1, columnspan=1, padx=1, pady=1, sticky="nsew")
            frm.configure(corner_radius=2)
            frm.grid()
            for child in frm.winfo_children(): child.pack_configure(padx=2, pady=2)
            
        slot_anterior = self.slot_maximized
        self.slot_maximized = None
        if ip_foco: self.trocar_qualidade(ip_foco, 102)
        
        # Restaura botão "Aumentar" no slot que estava maximizado
        if slot_anterior is not None:
             self.atualizar_botao_overlay(slot_anterior)

    def selecionar_slot(self, index):
        if not (0 <= index < 20): return
        for frm in self.slot_frames: frm.configure(border_color="black", border_width=2)
        ip_anterior = self.ip_selecionado
        self.slot_selecionado = index
        self.slot_frames[index].configure(border_color=self.ACCENT_RED, border_width=2)
        self.title(f"Monitoramento ABI - Espaço {index + 1} selecionado")
        self.entry_nome.pack_forget()
        self.container_info_topo.pack(side="left", padx=50, pady=5)
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
        else:
            if ip_anterior: self.pintar_botao(ip_anterior, "transparent")
            self.ip_selecionado = None
            self.entry_nome.delete(0, "end")
            self.lbl_nome_topo.configure(text="Nenhuma câmera selecionada")
            self.lbl_ip_topo.configure(text="")
            self.btn_renomear.configure(state="disabled")
        
        # Atualiza o botão sobreposto
        self.atualizar_botao_overlay(index)
        
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
        # Atualiza botão rodapé
        if self.slot_maximized is not None:
            self.btn_toggle_grid.configure(text="Minimizar camera", fg_color=self.GRAY_DARK, hover_color=self.TEXT_S)
        else:
            self.btn_toggle_grid.configure(text="Expandir camera", fg_color=self.ACCENT_WINE, hover_color=self.ACCENT_RED)

    def toggle_grid_layout(self):
        if self.slot_maximized is not None: self.restaurar_grid()
        else: self.maximizar_slot(self.slot_selecionado)
        self.atualizar_botoes_controle()

    def atribuir_ip_ao_slot(self, idx, ip):
        if not (0 <= idx < 20): return
        ip_antigo = self.grid_cameras[idx]
        self.grid_cameras[idx] = ip

        # Reset visual para estado padrão
        self.slot_frames[idx].configure(fg_color=self.BG_SIDEBAR)
        try: self.slot_labels[idx].configure(image="", fg_color="transparent")
        except: pass

        try:
            if ip == "0.0.0.0": self.slot_labels[idx].configure(text=f"Espaço {idx+1}")
            else: self.slot_labels[idx].configure(text=f"CONECTANDO\n{ip}")
        except: pass
        self.slot_labels[idx].image = None
        self.update_idletasks()
        self.salvar_grid()
        if ip_antigo and ip_antigo != "0.0.0.0" and ip_antigo != ip and ip_antigo not in self.grid_cameras:
            if ip_antigo in self.camera_handlers:
                try: self.camera_handlers[ip_antigo].parar()
                except: pass
                del self.camera_handlers[ip_antigo]
        if ip != "0.0.0.0":
            if ip in self.cooldown_conexoes: del self.cooldown_conexoes[ip]
            self.iniciar_conexao_assincrona(ip, 102)

    def selecionar_camera(self, ip):
        if self.slot_selecionado is not None:
            self.atribuir_ip_ao_slot(self.slot_selecionado, ip)
            self.selecionar_slot(self.slot_selecionado)

    def pintar_botao(self, ip, cor):
        if ip and ip in self.botoes_referencia: self.botoes_referencia[ip]['frame'].configure(fg_color=cor)

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

    def _processar_fila_conexoes_pendentes(self):
        """Worker que inicia conexões uma a uma para evitar erro 500 do servidor"""
        while True:
            try:
                if not self.fila_pendente_conexoes.empty():
                    ip, canal = self.fila_pendente_conexoes.get()
                    self._iniciar_conexao_real(ip, canal)
                    time.sleep(0.3) # Delay entre disparos de threads
                else:
                    time.sleep(0.1)
            except:
                time.sleep(1)

    def iniciar_conexao_assincrona(self, ip, canal=102):
        if not ip or ip == "0.0.0.0": return
        agora = time.time()
        if ip in self.cooldown_conexoes:
            if agora - self.cooldown_conexoes[ip] < 3: return
        if ip in self.camera_handlers:
            handler = self.camera_handlers[ip]
            if handler == "CONECTANDO": return
            if hasattr(handler, 'rodando') and handler.rodando: return
            del self.camera_handlers[ip]
        self.camera_handlers[ip] = "CONECTANDO"
        self.fila_pendente_conexoes.put((ip, canal))

    def _iniciar_conexao_real(self, ip, canal):
        threading.Thread(target=self._thread_conectar, args=(ip, canal), daemon=True).start()

    def _thread_conectar(self, ip, canal):
        tentativas = 3
        nova_cam = None
        sucesso = False

        for i in range(tentativas):
            try:
                url = f"rtsp://admin:1357gov%40@{ip}:554/Streaming/Channels/{canal}"
                nova_cam = CameraHandler(url, canal)
                sucesso = nova_cam.iniciar()
                if sucesso:
                    break
            except Exception as e:
                print(f"Tentativa {i+1} falhou para {ip}: {e}")

            if not sucesso:
                time.sleep(0.5) # Aguarda antes da próxima tentativa

        self.fila_conexoes.put((sucesso, nova_cam, ip))

    def _pos_conexao(self, sucesso, camera_obj, ip):
        if sucesso:
            self.camera_handlers[ip] = camera_obj
            if ip in self.cooldown_conexoes: del self.cooldown_conexoes[ip]
            # Sucesso: Garantir que o fundo volte ao normal
            for i, grid_ip in enumerate(self.grid_cameras):
                if grid_ip == ip:
                    self.slot_frames[i].configure(fg_color=self.BG_SIDEBAR)
                    self.slot_labels[i].configure(fg_color="transparent")
        else:
            if ip in self.camera_handlers: del self.camera_handlers[ip]
            self.cooldown_conexoes[ip] = time.time()
            for i, grid_ip in enumerate(self.grid_cameras):
                if grid_ip == ip:
                    try:
                        self.slot_labels[i].configure(text=f"ERRO AO CONECTAR\n{ip}", fg_color=self.ACCENT_RED)
                        self.slot_frames[i].configure(fg_color=self.ACCENT_RED)
                    except: pass
        self.atualizar_botoes_controle()

    def loop_exibicao(self):
        try:
            while not self.fila_conexoes.empty():
                try:
                    sucesso, camera_obj, ip = self.fila_conexoes.get_nowait()
                    self._pos_conexao(sucesso, camera_obj, ip)
                except: pass

            agora = time.time()
            indices = [self.slot_maximized] if self.slot_maximized is not None else range(20)

            raw_frames_cache = {}  # ip -> frame original
            processed_images_cache = {}  # (ip, w, h) -> ctk_img

            for i in indices:
                ip = self.grid_cameras[i]
                if not ip or ip == "0.0.0.0": continue

                # Gerenciamento de erro
                if ip in self.cooldown_conexoes:
                    if agora - self.cooldown_conexoes[ip] < 3:
                        try:
                            self.slot_labels[i].configure(text=f"ERRO AO CONECTAR\n{ip}", fg_color=self.ACCENT_RED)
                            self.slot_frames[i].configure(fg_color=self.ACCENT_RED)
                        except: pass
                        continue
                    else:
                        # Cooldown expirou, resetar para tentar novamente
                        self.slot_frames[i].configure(fg_color=self.BG_SIDEBAR)
                        self.slot_labels[i].configure(fg_color="transparent")

                # Busca ou obtém frame do handler
                if ip not in raw_frames_cache:
                    handler = self.camera_handlers.get(ip)
                    if handler is None:
                        self.iniciar_conexao_assincrona(ip, 102)
                        raw_frames_cache[ip] = None
                        continue
                    if handler == "CONECTANDO":
                        raw_frames_cache[ip] = None
                        continue
                    raw_frames_cache[ip] = handler.pegar_frame()

                frame = raw_frames_cache[ip]
                if frame is not None:
                    try:
                        w = self.slot_frames[i].winfo_width()
                        h = self.slot_frames[i].winfo_height()
                        w = max(10, w - 6); h = max(10, h - 6)

                        cache_key = (ip, w, h)
                        if cache_key in processed_images_cache:
                            ctk_img = processed_images_cache[cache_key]
                        else:
                            # Otimização: INTER_NEAREST para grid (muito rápido), INTER_LINEAR apenas para maximizado
                            interp = cv2.INTER_LINEAR if self.slot_maximized is not None else cv2.INTER_NEAREST
                            frame_resized = cv2.resize(frame, (w, h), interpolation=interp)

                            pos = (10, h - 10)
                            cv2.putText(frame_resized, ip, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 2)
                            cv2.putText(frame_resized, ip, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

                            # Note: rgb_frame não é mais necessário aqui, pois já vem convertido do handler
                            pil_img = Image.fromarray(frame_resized)
                            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w, h))
                            processed_images_cache[cache_key] = ctk_img

                        try:
                            # Se está mostrando vídeo, garante fundo transparente
                            self.slot_labels[i].configure(image=ctk_img, text="", fg_color="transparent")
                            self.slot_frames[i].configure(fg_color=self.BG_SIDEBAR)
                        except: pass
                        self.slot_labels[i].image = ctk_img
                        
                        # Garante que o botão overlay (se existir neste slot) fique por cima do vídeo
                        if self.btn_overlay_cam and self.slot_selecionado == i:
                             self.btn_overlay_cam.lift()
                             
                    except: pass
        except Exception as e: print(f"Erro no loop de exibição: {e}")
        finally: self.after(50, self.loop_exibicao)

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
            self.container_info_topo.pack(side="left", padx=50, pady=5)
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
            messagebox.showinfo("Presets", f"Predefinição '{nome}' salva com sucesso!")

    def aplicar_preset(self, nome):
        preset = self.presets.get(nome)
        if preset:
            for i, ip in enumerate(preset):
                if i < 20:
                    self.atribuir_ip_ao_slot(i, ip)
            self.selecionar_slot(self.slot_selecionado)
            messagebox.showinfo("Presets", f"Predefinição '{nome}' aplicada!")

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
        # Limpar lista atual
        for child in self.scroll_presets.winfo_children():
            child.destroy()

        # Rebuild em ordem alfabética
        for nome in sorted(self.presets.keys()):
            frm = ctk.CTkFrame(self.scroll_presets, height=45, fg_color="transparent", border_width=1, border_color=self.GRAY_DARK)
            frm.pack(fill="x", pady=2)
            frm.pack_propagate(False)

            lbl = ctk.CTkLabel(frm, text=nome, font=("Roboto", 13), anchor="w", cursor="hand2")
            lbl.pack(side="left", fill="both", expand=True, padx=10)
            lbl.bind("<Button-1>", lambda e, n=nome: self.aplicar_preset(n))

            # Botões de ação pequenos
            btn_ren = ctk.CTkButton(frm, text="R", width=30, height=30, fg_color=self.GRAY_DARK,
                                     hover_color=self.TEXT_S, command=lambda n=nome: self.renomear_preset(n))
            btn_ren.pack(side="right", padx=2)

            btn_del = ctk.CTkButton(frm, text="X", width=30, height=30, fg_color=self.ACCENT_WINE,
                                     hover_color=self.ACCENT_RED, command=lambda n=nome: self.deletar_preset(n))
            btn_del.pack(side="right", padx=5)

if __name__ == "__main__":
    app = CentralMonitoramento()
    app.mainloop()
