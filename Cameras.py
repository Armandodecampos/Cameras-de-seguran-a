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
    def __init__(self, url):
        self.url = url
        self.cap = None
        self.rodando = False
        self.frame_atual = None
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
        self.status_rede = {}
        
        self.ip_selecionado = None
        self.camera_handler = None
        self.em_tela_cheia = False
        self.id_request_atual = 0 

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

        # Rodapé (Botão Ligar) - Criamos antes para controlar a ordem do Pack
        self.btn_power = ctk.CTkButton(self.main_frame, text="SELECIONE UMA CÂMERA", state="disabled",
                                       height=50, font=("Arial", 16, "bold"), command=self.alternar_estado_stream)
        self.btn_power.pack(side="bottom", fill="x", padx=50, pady=20)

        # Display (Vídeo) - Pack por último com expand=True para ocupar o meio
        self.video_display = ctk.CTkLabel(self.main_frame, text="SINAL DESLIGADO", 
                                          font=("Arial", 20), fg_color="black", corner_radius=0)
        self.video_display.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 10))

        # Inicialização
        self.criar_botoes_iniciais()
        threading.Thread(target=self.monitor_rede_seguro, daemon=True).start()

    # --- LÓGICA DE SELEÇÃO DE CÂMERA (CORRIGIDA) ---
    def selecionar_camera(self, ip):
        if self.ip_selecionado == ip: return

        ip_anterior = self.ip_selecionado
        
        # 1. Atualiza a variável PRIMEIRO
        self.ip_selecionado = ip
        
        # 2. Reseta a cor do botão anterior (agora que a variável mudou, ele aceitará a cor da rede)
        if ip_anterior and ip_anterior in self.botoes_referencia:
            cor_rede = self.status_rede.get(ip_anterior, "transparent")
            self.pintar_botao(ip_anterior, cor_rede)
        
        # 3. Pinta o novo de azul
        self.pintar_botao(ip, "#1F6AA5")
        
        # Atualiza input de nome
        self.entry_nome.delete(0, "end")
        self.entry_nome.insert(0, self.dados_cameras.get(ip, ""))

        # Lógica de conexão (Anti-Lag)
        self.id_request_atual += 1
        if self.camera_handler and self.camera_handler.conectado:
            self.iniciar_conexao_assincrona(ip, self.id_request_atual)
        else:
            self.btn_power.configure(state="normal", text=f"LIGAR: {ip}", fg_color="#1f538d")
            self.video_display.configure(image=None, text=f"CÂMERA {ip}\nPRONTA PARA CONEXÃO")

    def pintar_botao(self, ip, cor):
        """Aplica a cor, mas respeita a seleção azul."""
        if ip not in self.botoes_referencia: return
        
        # Se este IP for o selecionado, FORÇA AZUL, ignora o monitor de rede
        if ip == self.ip_selecionado:
            self.botoes_referencia[ip].configure(fg_color="#1F6AA5")
        else:
            # Se não for o selecionado, aplica a cor solicitada (verde/vermelho/transparent)
            self.botoes_referencia[ip].configure(fg_color=cor)

    # --- TELA CHEIA (MAXIMIZAÇÃO TOTAL) ---
    def entrar_tela_cheia(self):
        if self.em_tela_cheia: return
        self.em_tela_cheia = True

        # 1. Ativa Fullscreen Real do Windows
        self.attributes("-fullscreen", True)

        # 2. Esconde painéis laterais e de controle
        self.sidebar.grid_forget()
        self.painel_topo.pack_forget()
        self.btn_power.pack_forget()

        # 3. Botão Flutuante para Voltar
        self.btn_fs_back = ctk.CTkButton(self.main_frame, text="✖ SAIR", width=80, height=40,
                                         command=self.sair_tela_cheia, fg_color="#c62828", bg_color="black",
                                         font=("Arial", 12, "bold"))
        self.btn_fs_back.place(relx=0.95, rely=0.05, anchor="ne")

        # 4. Ajusta vídeo para ocupar 100%
        self.video_display.pack(expand=True, fill="both", padx=0, pady=0)

    def sair_tela_cheia(self):
        if not self.em_tela_cheia: return
        self.em_tela_cheia = False

        # 1. Desativa Fullscreen
        self.attributes("-fullscreen", False)

        # 2. Remove botão flutuante
        if hasattr(self, 'btn_fs_back'): self.btn_fs_back.destroy()

        # 3. Restaura Sidebar
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # 4. CRÍTICO: Limpa o main_frame e re-adiciona na ORDEM CORRETA para não quebrar o layout
        self.painel_topo.pack_forget()
        self.video_display.pack_forget()
        self.btn_power.pack_forget()

        # Ordem de empacotamento: Topo -> Base -> Centro (Video)
        self.painel_topo.pack(side="top", fill="x", padx=10, pady=10)
        self.btn_power.pack(side="bottom", fill="x", padx=50, pady=20)
        self.video_display.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 10))

    # --- STREAMING ---
    def alternar_estado_stream(self):
        if not self.ip_selecionado: return

        if self.camera_handler and self.camera_handler.rodando:
            self.parar_stream_atual()
            self.btn_power.configure(text=f"LIGAR: {self.ip_selecionado}", fg_color="#1f538d")
            self.video_display.configure(image=None, text="SINAL DESLIGADO")
        else:
            self.id_request_atual += 1
            self.iniciar_conexao_assincrona(self.ip_selecionado, self.id_request_atual)

    def iniciar_conexao_assincrona(self, ip, request_id):
        self.parar_stream_atual()
        self.btn_power.configure(text="CONECTANDO...", state="disabled", fg_color="#555")
        self.video_display.configure(text="AGUARDE...")
        self.update()
        threading.Thread(target=self._thread_conectar, args=(ip, request_id), daemon=True).start()

    def _thread_conectar(self, ip, request_id):
        # URL Genérica Hikvision/Intelbras
        url = f"rtsp://admin:1357gov%40@{ip}:554/Streaming/Channels/101"
        nova_cam = CameraHandler(url)
        sucesso = nova_cam.iniciar()
        self.after(0, lambda: self._pos_conexao(sucesso, nova_cam, request_id))

    def _pos_conexao(self, sucesso, camera_obj, request_id):
        if request_id != self.id_request_atual:
            camera_obj.parar()
            return

        if sucesso:
            self.camera_handler = camera_obj
            self.btn_power.configure(text="DESLIGAR CÂMERA", fg_color="#B22222", state="normal")
            self.loop_exibicao()
        else:
            self.camera_handler = None
            self.video_display.configure(text="FALHA RTSP")
            self.btn_power.configure(text="TENTAR NOVAMENTE", fg_color="#D32F2F", state="normal")

    def parar_stream_atual(self):
        if self.camera_handler:
            self.camera_handler.parar()
            self.camera_handler = None

    def loop_exibicao(self):
        if not self.camera_handler or not self.camera_handler.rodando: return

        frame = self.camera_handler.pegar_frame()
        if frame is not None:
            # Obtém tamanho real da área de vídeo (seja tela cheia ou janela)
            w_disp = self.video_display.winfo_width()
            h_disp = self.video_display.winfo_height()
            
            # Proteção contra janelas minimizadas (tamanho 1)
            if w_disp < 10: w_disp = 640
            if h_disp < 10: h_disp = 360

            try:
                # Resize eficiente
                frame_resized = cv2.resize(frame, (w_disp, h_disp), interpolation=cv2.INTER_NEAREST)
                img_tk = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)))
                
                self.video_display.configure(image=img_tk, text="")
                self.video_display.image = img_tk
            except: pass
        
        self.after(15, self.loop_exibicao)

    # --- UTILITÁRIOS E DADOS ---
    def monitor_rede_seguro(self):
        while True:
            for ip in self.ips_unicos:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.1)
                    res = s.connect_ex((ip, 554))
                    s.close()
                    
                    nova_cor = "#2E7D32" if res == 0 else "transparent"
                    if res != 0 and self.status_rede.get(ip) == "#2E7D32": nova_cor = "#B71C1C"

                    if self.status_rede.get(ip) != nova_cor:
                        self.status_rede[ip] = nova_cor
                        self.after(0, lambda i=ip, c=nova_cor: self.pintar_botao(i, c))
                except: pass
                time.sleep(0.01)
            time.sleep(5)

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
            self.status_rede[ip] = "transparent"

if __name__ == "__main__":
    app = CentralMonitoramento()
    app.mainloop()