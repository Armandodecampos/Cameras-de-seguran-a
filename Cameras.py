import cv2
import customtkinter as ctk
from PIL import Image, ImageTk
import json
import os
import threading
import time
import socket

# Configuração de baixa latência para OpenCV/FFMPEG
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp;analyzeduration;50000;probesize;50000;fflags;nobuffer;flags;low_delay;max_delay;0;bf;0"

# --- CLASSE DE VÍDEO OTIMIZADA (SEM TRAVAMENTOS) ---
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
            # Buffersize=1 e backend FFMPEG para menor latência
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
                time.sleep(0.05) # Pequena pausa se perder sinal para não fritar CPU

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
    def __init__(self):
        super().__init__()

        self.title("Sistema de Monitoramento ABI - Full Control V3")
        self.geometry("1200x800")
        ctk.set_appearance_mode("Dark")

        # Bind da tecla ESC para sair da tela cheia
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

        # --- LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. BARRA LATERAL
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(self.sidebar, text="CÂMERAS", font=("Roboto", 20, "bold")).pack(pady=(15, 5))

        # Busca
        self.frame_busca = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_busca.pack(fill="x", padx=10, pady=5)

        self.entry_busca = ctk.CTkEntry(self.frame_busca, placeholder_text="Filtrar...")
        self.entry_busca.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_busca.bind("<KeyRelease>", lambda e: self.filtrar_lista())

        ctk.CTkButton(self.frame_busca, text="🔍", width=40, command=self.filtrar_lista, fg_color="#444").pack(side="left")

        self.scroll_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.scroll_frame.pack(expand=True, fill="both", padx=5, pady=5)

        # 2. ÁREA PRINCIPAL (Direita)
        self.main_frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")

        # Topo (Controles)
        self.painel_topo = ctk.CTkFrame(self.main_frame, fg_color="#2b2b2b", height=50)
        self.painel_topo.pack(side="top", fill="x", padx=10, pady=10)

        self.entry_nome = ctk.CTkEntry(self.painel_topo, width=300, placeholder_text="Nome da câmera...")
        self.entry_nome.pack(side="left", padx=10, pady=5)

        self.btn_salvar = ctk.CTkButton(self.painel_topo, text="Salvar", command=self.salvar_nome,
                                        fg_color="#F57C00", hover_color="#E65100", width=80)
        self.btn_salvar.pack(side="left", padx=5)

        self.btn_fullscreen = ctk.CTkButton(self.painel_topo, text="TELA CHEIA [ESC]", command=self.entrar_tela_cheia,
                                            fg_color="#444", width=120)
        self.btn_fullscreen.pack(side="right", padx=10)

        # Rodapé (Controles Inferiores)
        self.painel_base = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.painel_base.pack(side="bottom", fill="x", padx=10, pady=10)

        # REMOVIDO: Botão Toggle Camera (Ligar/Desligar) a pedido do usuário

        self.btn_toggle_grid = ctk.CTkButton(self.painel_base, text="1 camera", fg_color="#1F6AA5",
                                            height=40, command=self.toggle_grid_layout)
        self.btn_toggle_grid.pack(side="left", expand=True, fill="x", padx=5)

        self.btn_limpar_slot = ctk.CTkButton(self.painel_base, text="LIMPAR SLOT", fg_color="#666",
                                            height=40, command=self.limpar_slot_atual)
        self.btn_limpar_slot.pack(side="left", padx=5)

        # Grid de Câmeras (Área Central)
        self.grid_frame = ctk.CTkFrame(self.main_frame, fg_color="black")
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 10))

        for i in range(4): self.grid_frame.grid_rowconfigure(i, weight=1)
        for i in range(5): self.grid_frame.grid_columnconfigure(i, weight=1)

        self.slot_frames = []
        self.slot_labels = []
        for i in range(20):
            row, col = i // 5, i % 5
            frm = ctk.CTkFrame(self.grid_frame, fg_color="#111", corner_radius=2, border_width=0)
            frm.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            frm.pack_propagate(False) # Impede que o frame mude de tamanho com a imagem

            lbl = ctk.CTkLabel(frm, text=f"ESPAÇO {i+1}", corner_radius=0)
            lbl.pack(expand=True, fill="both")

            # Click and Drag bindings
            frm.bind("<Button-1>", lambda e, idx=i: self.ao_pressionar_slot(e, idx))
            lbl.bind("<Button-1>", lambda e, idx=i: self.ao_pressionar_slot(e, idx))
            frm.bind("<ButtonRelease-1>", lambda e, idx=i: self.ao_soltar_slot(e, idx))
            lbl.bind("<ButtonRelease-1>", lambda e, idx=i: self.ao_soltar_slot(e, idx))

            self.slot_frames.append(frm)
            self.slot_labels.append(lbl)

        # Inicialização
        self.criar_botoes_iniciais()

        # Restaura textos do grid
        for i, ip in enumerate(self.grid_cameras):
            if ip: self.slot_labels[i].configure(text=f"CARREGANDO\n{ip}")

        self.selecionar_slot(0)
        self.restaurar_grid() # Garante que inicia no modo 20 câmeras
        self.alternar_todos_streams()
        
        # REMOVIDO: Inicialização automática em tela cheia
        # self.entrar_tela_cheia()
        
        self.loop_exibicao()

    # --- LÓGICA DO GRID ---
    def maximizar_slot(self, index):
        self.grid_frame.pack_configure(padx=0, pady=0)
        for i, frm in enumerate(self.slot_frames):
            if i == index:
                frm.grid_configure(row=0, column=0, rowspan=4, columnspan=5, padx=0, pady=0, sticky="nsew")
                frm.configure(corner_radius=0)
            else:
                frm.grid_forget()
        self.slot_maximized = index

        # Sobe qualidade da câmera focada
        ip = self.grid_cameras[index]
        if ip:
            self.trocar_qualidade(ip, 101)

    def ao_pressionar_slot(self, event, index):
        self.press_data = {"index": index, "x": event.x_root, "y": event.y_root}

    def ao_soltar_slot(self, event, index):
        if not self.press_data: return

        dist = ((event.x_root - self.press_data["x"])**2 + (event.y_root - self.press_data["y"])**2)**0.5

        if dist < 15: # Threshold para considerar como clique
            self.selecionar_slot(index)
        else:
            target_idx = self.encontrar_slot_por_coords(event.x_root, event.y_root)
            if target_idx is not None and target_idx != index:
                # Troca as câmeras no grid
                self.grid_cameras[index], self.grid_cameras[target_idx] = \
                    self.grid_cameras[target_idx], self.grid_cameras[index]

                # Atualiza labels caso não tenha vídeo rodando
                for idx in [index, target_idx]:
                    ip = self.grid_cameras[idx]
                    if not ip:
                        self.slot_labels[idx].configure(image=None, text=f"ESPAÇO {idx+1}")
                    elif ip not in self.camera_handlers:
                        self.slot_labels[idx].configure(image=None, text=f"CARREGANDO\n{ip}")

                self.salvar_grid()
                self.selecionar_slot(target_idx)

        self.press_data = None

    def encontrar_slot_por_coords(self, x_root, y_root):
        for i, frm in enumerate(self.slot_frames):
            fx, fy = frm.winfo_rootx(), frm.winfo_rooty()
            fw, fh = frm.winfo_width(), frm.winfo_height()
            if fx <= x_root <= fx + fw and fy <= y_root <= fy + fh:
                return i
        return None

    def restaurar_grid(self):
        self.grid_frame.pack_configure(padx=10, pady=(0, 10))
        # Identifica câmera que estava em foco para reduzir qualidade
        ip_foco = self.grid_cameras[self.slot_maximized] if self.slot_maximized is not None else None

        for i, frm in enumerate(self.slot_frames):
            row, col = i // 5, i % 5
            frm.grid_configure(row=row, column=col, rowspan=1, columnspan=1, padx=1, pady=1, sticky="nsew")
            frm.configure(corner_radius=2)
            frm.grid()
        self.slot_maximized = None

        # Reduz qualidade da que estava focada
        if ip_foco:
            self.trocar_qualidade(ip_foco, 102)

    def selecionar_slot(self, index):
        # Remove destaque do anterior
        self.slot_frames[self.slot_selecionado].configure(fg_color="#111", border_width=0)

        # Define novo slot
        self.slot_selecionado = index
        self.slot_frames[index].configure(fg_color="#1f538d", border_width=2, border_color="#FFF")

        # Se houver uma câmera no slot, seleciona ela na lista lateral para exibir o nome
        ip = self.grid_cameras[index]
        if ip:
            self.ip_selecionado = ip
            self.entry_nome.delete(0, "end")
            self.entry_nome.insert(0, self.dados_cameras.get(ip, ""))
            # Pinta o botão na lateral
            if ip in self.botoes_referencia:
                self.pintar_botao(ip, "#1F6AA5")
        else:
            # CORREÇÃO: Se selecionar slot vazio, limpa dados da seleção
            self.ip_selecionado = None
            self.entry_nome.delete(0, "end")
            # Remove seleção visual da lista lateral
            for btn in self.botoes_referencia.values():
                btn.configure(fg_color="transparent")

        self.atualizar_botoes_controle()

    def limpar_slot_atual(self):
        idx = self.slot_selecionado
        ip_antigo = self.grid_cameras[idx]
        self.grid_cameras[idx] = None
        
        # CORREÇÃO: Resetar texto para "ESPAÇO X" e limpar imagem
        self.slot_labels[idx].configure(image=None, text=f"ESPAÇO {idx+1}")
        self.slot_labels[idx].image = None
        self.salvar_grid()

        # Se o IP antigo não estiver mais em nenhum slot, encerra o handler
        if ip_antigo and ip_antigo not in self.grid_cameras:
            if ip_antigo in self.camera_handlers:
                if hasattr(self.camera_handlers[ip_antigo], 'parar'):
                    self.camera_handlers[ip_antigo].parar()
                del self.camera_handlers[ip_antigo]

        # CORREÇÃO: Limpa seleção explicitamente para evitar bugs
        self.ip_selecionado = None
        self.entry_nome.delete(0, "end")
        
        # Remove seleção visual da lista lateral
        for btn in self.botoes_referencia.values():
            btn.configure(fg_color="transparent")

        # Se estava maximizado neste slot, restaura o grid para ver o espaço vazio
        if self.slot_maximized == idx:
            self.restaurar_grid()

        self.atualizar_botoes_controle()
        self.focus_set() # Garante que o foco saia do botão

    def salvar_grid(self):
        try:
            with open(self.arquivo_grid, "w", encoding='utf-8') as f:
                json.dump(self.grid_cameras, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao salvar grid: {e}")

    def carregar_grid(self):
        if os.path.exists(self.arquivo_grid):
            try:
                with open(self.arquivo_grid, "r", encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return [None] * 20

    def alternar_todos_streams(self):
        # Liga todas as câmeras que estão no grid mas não estão rodando (em baixa qualidade)
        for ip in set(self.grid_cameras):
            if ip and ip not in self.camera_handlers:
                self.iniciar_conexao_assincrona(ip, 102)

    def atualizar_botoes_controle(self):
        # Atualiza botão de Grid (Expandir/Minimizar)
        if self.slot_maximized is not None:
            self.btn_toggle_grid.configure(text="20 cameras", fg_color="#444", hover_color="#333")
        else:
            self.btn_toggle_grid.configure(text="1 camera", fg_color="#1F6AA5", hover_color="#154a73")

    def toggle_grid_layout(self):
        if self.slot_maximized is not None:
            self.restaurar_grid()
        else:
            self.maximizar_slot(self.slot_selecionado)
        self.atualizar_botoes_controle()

    # --- LÓGICA DE SELEÇÃO DE CÂMERA (CORRIGIDA) ---
    def selecionar_camera(self, ip):
        ip_anterior_lateral = self.ip_selecionado
        self.ip_selecionado = ip

        if ip_anterior_lateral and ip_anterior_lateral in self.botoes_referencia:
            self.pintar_botao(ip_anterior_lateral, "transparent")

        self.pintar_botao(ip, "#1F6AA5")
        self.entry_nome.delete(0, "end")
        self.entry_nome.insert(0, self.dados_cameras.get(ip, ""))

        # Atribui ao slot selecionado e evita vazamento de conexões
        idx = self.slot_selecionado
        ip_antigo_slot = self.grid_cameras[idx]
        self.grid_cameras[idx] = ip
        self.slot_labels[idx].configure(image=None, text=f"CONECTANDO\n{ip}")
        self.salvar_grid()

        # Se o IP antigo não estiver mais em nenhum slot, encerra o handler
        if ip_antigo_slot and ip_antigo_slot != ip and ip_antigo_slot not in self.grid_cameras:
            if ip_antigo_slot in self.camera_handlers:
                if hasattr(self.camera_handlers[ip_antigo_slot], 'parar'):
                    self.camera_handlers[ip_antigo_slot].parar()
                del self.camera_handlers[ip_antigo_slot]

        # Inicia conexão se necessário (sempre 102 ao selecionar via grid)
        self.iniciar_conexao_assincrona(ip, 102)
        self.atualizar_botoes_controle()

    def pintar_botao(self, ip, cor):
        """Aplica a cor, mas respeita a seleção azul."""
        if ip not in self.botoes_referencia: return

        # Se este IP for o selecionado, FORÇA AZUL
        if ip == self.ip_selecionado:
            self.botoes_referencia[ip].configure(fg_color="#1F6AA5")
        else:
            # Se não for o selecionado, usa cor transparente (padrão)
            self.botoes_referencia[ip].configure(fg_color="transparent")

    # --- TELA CHEIA (MAXIMIZAÇÃO TOTAL) ---
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

        # Remove espaços entre câmeras
        for frm in self.slot_frames:
            frm.grid_configure(padx=0, pady=0, sticky="nsew")
            frm.configure(corner_radius=0)

        # Botão flutuante para sair
        self.btn_sair_fs = ctk.CTkButton(self.main_frame, text="✖ SAIR TELA CHEIA",
                                         width=150, height=40, fg_color="#c62828",
                                         hover_color="#b71c1c", font=("Arial", 12, "bold"),
                                         command=self.sair_tela_cheia)
        self.btn_sair_fs.place(relx=0.98, rely=0.02, anchor="ne")

    def sair_tela_cheia(self):
        if not self.em_tela_cheia: return
        self.em_tela_cheia = False
        self.attributes("-fullscreen", False)

        if hasattr(self, 'btn_sair_fs'):
            self.btn_sair_fs.destroy()

        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_configure(column=1, columnspan=1)

        # Restaura espaços entre câmeras
        for frm in self.slot_frames:
            frm.grid_configure(padx=1, pady=1, sticky="nsew")
            frm.configure(corner_radius=2)

        # Limpa e restaura ordem do pack
        self.painel_topo.pack_forget()
        self.painel_base.pack_forget()
        self.grid_frame.pack_forget()

        self.painel_topo.pack(side="top", fill="x", padx=10, pady=10)
        self.painel_base.pack(side="bottom", fill="x", padx=10, pady=10)
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 10))

    # --- STREAMING ---
    def trocar_qualidade(self, ip, novo_canal):
        """Reinicia o stream de uma câmera para trocar resolução (101 vs 102)."""
        if not ip: return
        handler = self.camera_handlers.get(ip)

        if handler and handler != "CONECTANDO":
            if getattr(handler, 'canal', 101) != novo_canal:
                handler.parar()
                del self.camera_handlers[ip]
                self.iniciar_conexao_assincrona(ip, novo_canal)

    def iniciar_conexao_assincrona(self, ip, canal=102):
        if not ip or ip in self.camera_handlers: return
        self.camera_handlers[ip] = "CONECTANDO"
        threading.Thread(target=self._thread_conectar, args=(ip, canal), daemon=True).start()

    def _thread_conectar(self, ip, canal):
        url = f"rtsp://admin:1357gov%40@{ip}:554/Streaming/Channels/{canal}"
        nova_cam = CameraHandler(url, canal)
        sucesso = nova_cam.iniciar()
        self.after(0, lambda: self._pos_conexao(sucesso, nova_cam, ip))

    def _pos_conexao(self, sucesso, camera_obj, ip):
        if sucesso:
            self.camera_handlers[ip] = camera_obj
        else:
            if ip in self.camera_handlers: del self.camera_handlers[ip]
        self.atualizar_botoes_controle()

    def loop_exibicao(self):
        # OTIMIZAÇÃO: Processa apenas os slots visíveis
        indices = [self.slot_maximized] if self.slot_maximized is not None else range(20)

        for i in indices:
            ip = self.grid_cameras[i]
            if not ip: continue
            handler = self.camera_handlers.get(ip)
            if not handler or handler == "CONECTANDO": continue

            # Só processa se houver um frame novo (otimiza CPU da thread principal)
            frame = handler.pegar_frame()
            if frame is not None:
                try:
                    # Usa o tamanho do Frame (fixo pelo grid) em vez do Label
                    w = self.slot_frames[i].winfo_width()
                    h = self.slot_frames[i].winfo_height()

                    # Desconta bordas se houver
                    bw = self.slot_frames[i].cget("border_width")
                    if bw > 0:
                        w -= 2*bw
                        h -= 2*bw

                    if w < 10: w, h = 300, 200

                    # OTIMIZAÇÃO: Redimensiona antes de converter cores (mais rápido)
                    frame_resized = cv2.resize(frame, (w, h), interpolation=cv2.INTER_NEAREST)

                    # Overlay do IP na imagem (Sombra + Texto para melhor legibilidade)
                    pos = (10, h - 10)
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    scale = 0.5
                    cv2.putText(frame_resized, ip, pos, font, scale, (0, 0, 0), 2, cv2.LINE_AA)
                    cv2.putText(frame_resized, ip, pos, font, scale, (255, 255, 255), 1, cv2.LINE_AA)

                    img_tk = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)))
                    self.slot_labels[i].configure(image=img_tk, text="")
                    self.slot_labels[i].image = img_tk
                except: pass

        # OTIMIZAÇÃO: Intervalo de 40ms (25 FPS) para poupar CPU
        self.after(40, self.loop_exibicao)

    # --- UTILITÁRIOS E DADOS ---
    def filtrar_lista(self):
        termo = self.entry_busca.get().lower()
        for ip, btn in self.botoes_referencia.items():
            nome = self.dados_cameras.get(ip, "").lower()
            if termo in ip or termo in nome:
                btn.pack(fill="x", pady=2)
            else:
                btn.pack_forget()

    def salvar_nome(self):
        if self.ip_selecionado:
            novo_nome = self.entry_nome.get()
            self.dados_cameras[self.ip_selecionado] = novo_nome
            with open(self.arquivo_config, "w", encoding='utf-8') as f:
                json.dump(self.dados_cameras, f, ensure_ascii=False, indent=4)
            self.botoes_referencia[self.ip_selecionado].configure(text=f"{novo_nome}\n{self.ip_selecionado}")

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

    def criar_botoes_iniciais(self):
        for ip in self.ips_unicos:
            nome = self.dados_cameras.get(ip, f"IP {ip}")
            btn = ctk.CTkButton(self.scroll_frame, text=f"{nome}\n{ip}", anchor="w", height=45,
                                fg_color="transparent", border_width=1, border_color="#333",
                                command=lambda x=ip: self.selecionar_camera(x))
            btn.pack(fill="x", pady=2)
            self.botoes_referencia[ip] = btn

if __name__ == "__main__":
    app = CentralMonitoramento()
    app.mainloop()
