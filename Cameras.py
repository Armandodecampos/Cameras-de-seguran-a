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
        self.camera_handlers = {}
        self.em_tela_cheia = False
        self.id_request_atual = 0
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

        self.btn_power = ctk.CTkButton(self.painel_base, text="LIGAR TODOS",
                                       height=40, font=("Arial", 14, "bold"), command=self.alternar_todos_streams)
        self.btn_power.pack(side="left", expand=True, fill="x", padx=5)

        self.btn_limpar_slot = ctk.CTkButton(self.painel_base, text="LIMPAR SLOT", fg_color="#666",
                                            height=40, command=self.limpar_slot_atual)
        self.btn_limpar_slot.pack(side="left", padx=5)

        # Grid de Câmeras (Área Central)
        self.grid_frame = ctk.CTkFrame(self.main_frame, fg_color="black")
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 10))

        for i in range(4): self.grid_frame.grid_rowconfigure(i, weight=1)
        for i in range(5): self.grid_frame.grid_columnconfigure(i, weight=1)

        self.slot_labels = []
        for i in range(20):
            row, col = i // 5, i % 5
            lbl = ctk.CTkLabel(self.grid_frame, text=f"ESPAÇO {i+1}",
                               fg_color="#111", corner_radius=2)
            lbl.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            lbl.bind("<Button-1>", lambda e, idx=i: self.selecionar_slot(idx))
            self.slot_labels.append(lbl)

        # Inicialização
        self.criar_botoes_iniciais()
        self.selecionar_slot(0)
        self.alternar_todos_streams()
        self.loop_exibicao()
        threading.Thread(target=self.monitor_rede_seguro, daemon=True).start()

    # --- LÓGICA DO GRID ---
    def selecionar_slot(self, index):
        # Remove destaque do anterior
        self.slot_labels[self.slot_selecionado].configure(fg_color="#111", border_width=0)

        # Define novo slot
        self.slot_selecionado = index
        self.slot_labels[index].configure(fg_color="#1f538d", border_width=2, border_color="#FFF")

        # Se houver uma câmera no slot, seleciona ela na lista lateral para exibir o nome
        ip = self.grid_cameras[index]
        if ip:
            self.ip_selecionado = ip
            self.entry_nome.delete(0, "end")
            self.entry_nome.insert(0, self.dados_cameras.get(ip, ""))
            # Pinta o botão na lateral
            if ip in self.botoes_referencia:
                self.pintar_botao(ip, "#1F6AA5")

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
        # Liga todas as câmeras que estão no grid mas não estão rodando
        for ip in set(self.grid_cameras):
            if ip and ip not in self.camera_handlers:
                self.iniciar_conexao_assincrona(ip)

    # --- LÓGICA DE SELEÇÃO DE CÂMERA (CORRIGIDA) ---
    def selecionar_camera(self, ip):
        ip_anterior_lateral = self.ip_selecionado
        self.ip_selecionado = ip

        if ip_anterior_lateral and ip_anterior_lateral in self.botoes_referencia:
            cor_rede = self.status_rede.get(ip_anterior_lateral, "transparent")
            self.pintar_botao(ip_anterior_lateral, cor_rede)

        self.pintar_botao(ip, "#1F6AA5")
        self.entry_nome.delete(0, "end")
        self.entry_nome.insert(0, self.dados_cameras.get(ip, ""))

        # Atribui ao slot selecionado e evita vazamento de conexões
        idx = self.slot_selecionado
        ip_antigo_slot = self.grid_cameras[idx]
        self.grid_cameras[idx] = ip
        self.salvar_grid()

        # Se o IP antigo não estiver mais em nenhum slot, encerra o handler
        if ip_antigo_slot and ip_antigo_slot != ip and ip_antigo_slot not in self.grid_cameras:
            if ip_antigo_slot in self.camera_handlers:
                if hasattr(self.camera_handlers[ip_antigo_slot], 'parar'):
                    self.camera_handlers[ip_antigo_slot].parar()
                del self.camera_handlers[ip_antigo_slot]

        # Inicia conexão se necessário
        self.iniciar_conexao_assincrona(ip)

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
        self.attributes("-fullscreen", True)
        self.sidebar.grid_forget()
        self.painel_topo.pack_forget()
        self.painel_base.pack_forget()
        self.grid_frame.pack(expand=True, fill="both", padx=0, pady=0)

    def sair_tela_cheia(self):
        if not self.em_tela_cheia: return
        self.em_tela_cheia = False
        self.attributes("-fullscreen", False)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.painel_topo.pack(side="top", fill="x", padx=10, pady=10)
        self.painel_base.pack(side="bottom", fill="x", padx=10, pady=10)
        self.grid_frame.pack(side="top", expand=True, fill="both", padx=10, pady=(0, 10))

    # --- STREAMING ---
    def iniciar_conexao_assincrona(self, ip):
        if not ip or ip in self.camera_handlers: return
        self.camera_handlers[ip] = "CONECTANDO"
        threading.Thread(target=self._thread_conectar, args=(ip,), daemon=True).start()

    def _thread_conectar(self, ip):
        url = f"rtsp://admin:1357gov%40@{ip}:554/Streaming/Channels/101"
        nova_cam = CameraHandler(url)
        sucesso = nova_cam.iniciar()
        self.after(0, lambda: self._pos_conexao(sucesso, nova_cam, ip))

    def _pos_conexao(self, sucesso, camera_obj, ip):
        if sucesso:
            self.camera_handlers[ip] = camera_obj
        else:
            if ip in self.camera_handlers: del self.camera_handlers[ip]

    def loop_exibicao(self):
        for i, ip in enumerate(self.grid_cameras):
            if not ip: continue
            handler = self.camera_handlers.get(ip)
            if not handler or handler == "CONECTANDO": continue

            frame = handler.pegar_frame()
            if frame is not None:
                try:
                    w = self.slot_labels[i].winfo_width()
                    h = self.slot_labels[i].winfo_height()
                    if w < 10: w, h = 300, 200

                    frame_resized = cv2.resize(frame, (w, h), interpolation=cv2.INTER_NEAREST)
                    img_tk = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)))
                    self.slot_labels[i].configure(image=img_tk, text="")
                    self.slot_labels[i].image = img_tk
                except: pass

        self.after(30, self.loop_exibicao)

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