import os
# Otimização FFMPEG para baixo delay e conexão confiável
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp;analyzeduration;1000000;probesize;1000000"

import cv2
import customtkinter as ctk
from PIL import Image, ImageTk
import json
import os
import threading
import time
import socket

# --- CLASSE DE VÍDEO OTIMIZADA (SEM TRAVAMENTOS) ---
class CameraHandler:
    def __init__(self, url, channel=102):
        self.url = url
        self.channel = channel
        self.cap = None
        self.rodando = False
        self.frame_atual = None
        self.frame_novo = False
        self.lock = threading.Lock()
        self.conectado = False

    def iniciar(self):
        for tentativa in range(3):
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
                    if self.cap:
                        self.cap.release()
                    print(f"Tentativa {tentativa + 1} falhou para {self.url}")
                    if tentativa < 2:
                        time.sleep(1)
            except Exception as e:
                print(f"Erro na tentativa {tentativa + 1}: {e}")
                if tentativa < 2:
                    time.sleep(1)
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
            return self.frame_atual

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
        self.ip_pre_selecionado = None
        self.camera_handlers = {}
        self.em_tela_cheia = False
        self.slot_maximized = None
        self.arquivo_grid = os.path.join(os.path.expanduser("~"), "grid_config_abi.json")
        self.grid_cameras = self.carregar_grid()
        self.slot_selecionado = 0

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

        self.btn_toggle_cam = ctk.CTkButton(self.painel_base, text="LIGAR CAM", fg_color="#2E7D32", hover_color="#1B5E20",
                                           height=40, command=self.toggle_camera_selecionada)
        self.btn_toggle_cam.pack(side="left", expand=True, fill="x", padx=5)

        self.btn_toggle_grid = ctk.CTkButton(self.painel_base, text="EXPANDIR", fg_color="#1F6AA5",
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

            # Click binding on both frame and label
            frm.bind("<Button-1>", lambda e, idx=i: self.selecionar_slot(idx))
            lbl.bind("<Button-1>", lambda e, idx=i: self.selecionar_slot(idx))

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
        self.loop_exibicao()

    # --- LÓGICA DO GRID ---
    def maximizar_slot(self, index):
        for i, frm in enumerate(self.slot_frames):
            if i == index:
                frm.grid_configure(row=0, column=0, rowspan=4, columnspan=5)
            else:
                frm.grid_forget()
        self.slot_maximized = index

        # Aumenta qualidade da câmera maximizada para Main Stream (101)
        ip = self.grid_cameras[index]
        self.trocar_qualidade(ip, 101)

    def restaurar_grid(self):
        for i, frm in enumerate(self.slot_frames):
            row, col = i // 5, i % 5
            frm.grid_configure(row=row, column=col, rowspan=1, columnspan=1)
            frm.grid()

        # Volta qualidade para Sub Stream (102) para todas no grid
        if self.slot_maximized is not None:
            ip = self.grid_cameras[self.slot_maximized]
            self.trocar_qualidade(ip, 102)

        self.slot_maximized = None

    def selecionar_slot(self, index):
        # Se houver uma câmera pré-selecionada na lista lateral, atribui ela a este slot
        if self.ip_pre_selecionado:
            ip = self.ip_pre_selecionado
            ip_antigo_slot = self.grid_cameras[index]

            self.grid_cameras[index] = ip
            self.slot_labels[index].configure(image=None, text=f"CONECTANDO\n{ip}")
            self.salvar_grid()

            # Limpa handler antigo se não estiver mais em uso
            if ip_antigo_slot and ip_antigo_slot != ip and ip_antigo_slot not in self.grid_cameras:
                if ip_antigo_slot in self.camera_handlers:
                    if hasattr(self.camera_handlers[ip_antigo_slot], 'parar'):
                        self.camera_handlers[ip_antigo_slot].parar()
                    del self.camera_handlers[ip_antigo_slot]

            self.iniciar_conexao_assincrona(ip, channel=102)

            # Limpa pré-seleção
            self.pintar_botao(self.ip_pre_selecionado, False)
            self.ip_pre_selecionado = None
            self.atualizar_botoes_controle()
            return

        # Lógica de Maximizar/Restaurar (apenas se clicar no mesmo slot selecionado)
        if self.slot_selecionado == index:
            if self.slot_maximized == index:
                self.restaurar_grid()
            else:
                self.maximizar_slot(index)
        else:
            if self.slot_maximized is not None:
                self.restaurar_grid()

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
            # Marca na lista lateral que esta câmera está "ativa" (apenas visual)
            if ip in self.botoes_referencia:
                self.pintar_botao(ip, True)

        self.atualizar_botoes_controle()

    def limpar_slot_atual(self):
        idx = self.slot_selecionado
        ip_antigo = self.grid_cameras[idx]
        self.grid_cameras[idx] = None
        self.slot_labels[idx].configure(image=None, text=f"ESPAÇO {idx+1}")
        self.salvar_grid()

        # Se o IP antigo não estiver mais em nenhum slot, encerra o handler
        if ip_antigo and ip_antigo not in self.grid_cameras:
            if ip_antigo in self.camera_handlers:
                if hasattr(self.camera_handlers[ip_antigo], 'parar'):
                    self.camera_handlers[ip_antigo].parar()
                del self.camera_handlers[ip_antigo]

        self.atualizar_botoes_controle()

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
        # Liga todas as câmeras que estão no grid mas não estão rodando (Qualidade Baixa)
        for ip in set(self.grid_cameras):
            if ip and ip not in self.camera_handlers:
                self.iniciar_conexao_assincrona(ip, channel=102)

    def trocar_qualidade(self, ip, channel):
        if not ip: return
        handler = self.camera_handlers.get(ip)
        if handler and isinstance(handler, CameraHandler) and handler.channel == channel:
            return

        # Para o atual se existir
        if handler and hasattr(handler, 'parar'):
            handler.parar()

        if ip in self.camera_handlers:
            del self.camera_handlers[ip]

        # Reinicia com nova qualidade
        self.iniciar_conexao_assincrona(ip, channel)

    def ligar_camera_selecionada(self):
        ip = self.grid_cameras[self.slot_selecionado]
        if ip:
            self.iniciar_conexao_assincrona(ip, channel=102)

    def desligar_camera_selecionada(self):
        ip = self.grid_cameras[self.slot_selecionado]
        if ip and ip in self.camera_handlers:
            handler = self.camera_handlers[ip]
            if hasattr(handler, 'parar'):
                handler.parar()
            del self.camera_handlers[ip]
            self.slot_labels[self.slot_selecionado].configure(image=None, text=f"DESLIGADO\n{ip}")

    def atualizar_botoes_controle(self):
        # Atualiza botão de Câmera (Ligar/Desligar)
        ip = self.grid_cameras[self.slot_selecionado]
        if not ip:
            self.btn_toggle_cam.configure(text="LIGAR CAM", fg_color="#2E7D32", state="disabled")
        else:
            self.btn_toggle_cam.configure(state="normal")
            if ip in self.camera_handlers:
                self.btn_toggle_cam.configure(text="DESLIGAR CAM", fg_color="#B71C1C", hover_color="#880E4F")
            else:
                self.btn_toggle_cam.configure(text="LIGAR CAM", fg_color="#2E7D32", hover_color="#1B5E20")

        # Atualiza botão de Grid (Expandir/Minimizar)
        if self.slot_maximized is not None:
            self.btn_toggle_grid.configure(text="MINIMIZAR (GRID 20)", fg_color="#444", hover_color="#333")
        else:
            self.btn_toggle_grid.configure(text="EXPANDIR (FOCAR)", fg_color="#1F6AA5", hover_color="#154a73")

    def toggle_camera_selecionada(self):
        ip = self.grid_cameras[self.slot_selecionado]
        if not ip: return
        if ip in self.camera_handlers:
            self.desligar_camera_selecionada()
        else:
            self.ligar_camera_selecionada()
        self.atualizar_botoes_controle()

    def toggle_grid_layout(self):
        if self.slot_maximized is not None:
            self.restaurar_grid()
        else:
            self.maximizar_slot(self.slot_selecionado)
        self.atualizar_botoes_controle()

    # --- LÓGICA DE SELEÇÃO DE CÂMERA (CORRIGIDA) ---
    def selecionar_camera(self, ip):
        # Desmarca anterior
        if self.ip_pre_selecionado:
            self.pintar_botao(self.ip_pre_selecionado, False)

        # Define nova pré-seleção
        self.ip_pre_selecionado = ip
        self.pintar_botao(ip, True)

        # Apenas atualiza o nome na entrada para referência
        self.entry_nome.delete(0, "end")
        self.entry_nome.insert(0, self.dados_cameras.get(ip, ""))

    def pintar_botao(self, ip, selecionado):
        """Aplica borda para indicar seleção."""
        if ip not in self.botoes_referencia: return
        btn = self.botoes_referencia[ip]

        if selecionado:
            btn.configure(border_width=2, border_color="#1F6AA5")
        else:
            btn.configure(border_width=1, border_color="#333")

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

        # Limpa e restaura ordem do pack
        self.painel_topo.pack_forget()
        self.painel_base.pack_forget()
        self.grid_frame.pack_forget()

        self.painel_topo.pack(side="top", fill="x", padx=10, pady=10)
        self.painel_base.pack(side="bottom", fill="x", padx=10, pady=10)
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 10))

    # --- STREAMING ---
    def iniciar_conexao_assincrona(self, ip, channel=102):
        if not ip or ip in self.camera_handlers: return
        self.camera_handlers[ip] = "CONECTANDO"
        threading.Thread(target=self._thread_conectar, args=(ip, channel), daemon=True).start()

    def _thread_conectar(self, ip, channel=102):
        # 101 = Qualidade Alta (Main Stream)
        # 102 = Qualidade Baixa (Sub Stream - Mais rápido/menos delay)
        url = f"rtsp://admin:1357gov%40@{ip}:554/Streaming/Channels/{channel}"
        nova_cam = CameraHandler(url, channel=channel)
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
            if not handler or handler == "CONECTANDO" or not handler.frame_novo:
                continue

            frame = handler.pegar_frame()
            if frame is not None:
                try:
                    # Reset do flag com lock para garantir consistência
                    with handler.lock:
                        handler.frame_novo = False

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