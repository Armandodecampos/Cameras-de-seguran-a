import sys
import os
import sqlite3
import re
import datetime
import traceback

# --- BLOCO DE PROTEÇÃO DE IMPORTAÇÃO ---
try:
    from PyQt6.QtCore import Qt, QUrl, QTimer, QSettings, QSize, pyqtSignal
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
        QLineEdit, QPushButton, QLabel, QSplitter, QTextEdit, QTextBrowser, QGroupBox,
        QStackedWidget, QTabBar, QMessageBox, QDialog, QFileDialog, QFrame,
        QRadioButton, QButtonGroup
    )
    from PyQt6.QtGui import QPixmap, QFont, QIcon, QAction, QImage
    from PyQt6.QtMultimedia import QCamera, QMediaCaptureSession, QVideoSink, QMediaDevices
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage, QWebEngineProfile
    import qrcode
    from PIL.ImageQt import ImageQt
except ImportError as e:
    print("\n" + "="*60)
    print("ERRO CRÍTICO: BIBLIOTECAS NÃO ENCONTRADAS")
    print("="*60)
    print(f"Erro detalhado: {e}")
    print("\nPara corrigir, abra o terminal e digite:")
    print("pip install PyQt6 PyQt6-WebEngine pillow qrcode")
    print("="*60 + "\n")
    sys.exit(1)

# --- CLASSE CUSTOMIZADA PARA NAVEGAÇÃO COM ABAS ---
class CustomWebPage(QWebEnginePage):
    """
    Página customizada que abre links em novas abas.
    """
    def __init__(self, profile, parent_view, browser_window):
        super().__init__(profile, parent_view)
        self.browser_window = browser_window

    def createWindow(self, _type):
        for i in range(self.browser_window.tabs.count()):
            if "Portaria Virtual" in self.browser_window.tabs.tabText(i):
                self.browser_window.tabs.setCurrentIndex(i)
                view = self.browser_window.web_stack.widget(i)
                if view:
                    return view.page()

        current_profile = self.profile()
        new_view = self.browser_window.add_new_tab(QUrl(""), "Nova Guia", profile=current_profile)
        return new_view.page()

class QRDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QR Code Gerado")
        self.setModal(True)
        self.setStyleSheet("background-color: white; color: black;")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)

        layout = QVBoxLayout(self)
        layout.addStretch()

        self.lbl_qr = QLabel()
        self.lbl_qr.setPixmap(pixmap)
        self.lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_qr)

        self.btn_close = QPushButton("Fechar")
        self.btn_close.setFixedWidth(200)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 8px;
                font-size: 16px;
                margin-top: 20px;
                border: none;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        layout.addWidget(self.btn_close, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        self.showFullScreen()

# --- NOVA CLASSE: DIÁLOGO DE CÂMERA ---
class CameraDialog(QDialog):
    # Sinal para atualizar a UI com o novo frame com segurança de thread (QImage é mais seguro para threads que QPixmap)
    frame_ready = pyqtSignal(QImage)

    def __init__(self, parent=None, camera_device=None):
        super().__init__(parent)
        self.setWindowTitle("Captura de Foto")
        self.setModal(True)
        self.setMinimumSize(500, 650)
        self.setStyleSheet("background-color: #f8fafc; color: #1e293b;")

        self.layout = QVBoxLayout(self)

        # Área de exibição da câmera
        self.lbl_video = QLabel("Iniciando câmera...")
        self.lbl_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_video.setStyleSheet("border: 2px solid #cbd5e1; background-color: black; border-radius: 8px;")
        # Proporção 120:141 -> 400x470 (aprox)
        self.lbl_video.setFixedSize(400, 470)
        self.layout.addWidget(self.lbl_video, alignment=Qt.AlignmentFlag.AlignCenter)

        # Botão principal de captura
        self.btn_capture = QPushButton("📸 Capturar Foto")
        self.btn_capture.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_capture.clicked.connect(self.capture_photo)
        self.layout.addWidget(self.btn_capture)

        # Container para botões pós-captura
        self.container_pos = QWidget()
        self.lay_pos = QHBoxLayout(self.container_pos)

        self.btn_download = QPushButton("💾 Baixar")
        self.btn_download.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; font-weight: bold; padding: 12px; border-radius: 8px; }
            QPushButton:hover { background-color: #059669; }
        """)

        self.btn_cancel = QPushButton("✖ Cancelar")
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; font-weight: bold; padding: 12px; border-radius: 8px; }
            QPushButton:hover { background-color: #dc2626; }
        """)

        self.lay_pos.addWidget(self.btn_download)
        self.lay_pos.addWidget(self.btn_cancel)
        self.container_pos.hide()
        self.layout.addWidget(self.container_pos)

        self.btn_download.clicked.connect(self.save_photo)
        self.btn_cancel.clicked.connect(self.reset_camera)

        # Configuração da Câmera
        if camera_device is None:
            camera_device = QMediaDevices.defaultVideoInput()
        self.camera = QCamera(camera_device)
        self.session = QMediaCaptureSession()
        self.sink = QVideoSink()

        self.session.setCamera(self.camera)
        self.session.setVideoSink(self.sink)

        self.sink.videoFrameChanged.connect(self.on_frame_changed)
        self.frame_ready.connect(self.update_ui_frame)

        self.captured_image = None
        self.last_image = None
        self.camera.start()

    def on_frame_changed(self, frame):
        if self.container_pos.isVisible():
            return

        img = frame.toImage()
        if img.isNull():
            return

        # Forçar Proporção 120:141
        w, h = img.width(), img.height()
        target_ratio = 120 / 141

        if w / h > target_ratio:
            # Muito largo, corta laterais
            new_w = int(h * target_ratio)
            offset = (w - new_w) // 2
            img = img.copy(offset, 0, new_w, h)
        else:
            # Muito alto, corta topo/fundo
            new_h = int(w / target_ratio)
            offset = (h - new_h) // 2
            img = img.copy(0, offset, w, new_h)

        self.last_image = img
        self.frame_ready.emit(img)

    def update_ui_frame(self, image):
        pixmap = QPixmap.fromImage(image)
        self.lbl_video.setPixmap(pixmap.scaled(
            self.lbl_video.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

    def capture_photo(self):
        if self.last_image:
            self.captured_image = self.last_image
            self.btn_capture.hide()
            self.container_pos.show()

    def reset_camera(self):
        self.container_pos.hide()
        self.btn_capture.show()
        self.captured_image = None

    def save_photo(self):
        if self.captured_image:
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads", "foto_visitante.jpg")
            fname, _ = QFileDialog.getSaveFileName(self, "Salvar Foto", downloads_path, "Images (*.jpg *.png)")
            if fname:
                if self.captured_image.save(fname):
                    QMessageBox.information(self, "Sucesso", "Foto salva com sucesso!")
                    self.accept()
                else:
                    QMessageBox.critical(self, "Erro", "Falha ao salvar a foto.")

    def closeEvent(self, event):
        self.camera.stop()
        super().closeEvent(event)

# --- NOVA CLASSE: DIÁLOGO DE CONFIGURAÇÕES ---
class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("Configurações do Sistema")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        # Define estilo base do diálogo para garantir legibilidade
        self.setStyleSheet("""
            QDialog { font-size: 14px; }
            QGroupBox { font-weight: bold; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 10px; padding-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; }
        """)

        layout = QVBoxLayout(self)

        # === SEÇÃO BANCO DE DADOS ===
        gb_db = QGroupBox("Gerenciamento de Banco de Dados")
        lay_db = QVBoxLayout(gb_db)
        
        # Status atual
        status_text = self.parent_window.lbl_status_db.text()
        self.lbl_status = QLabel(status_text)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Copia o estilo do label original, mas ajusta se necessário
        if "Nenhum" in status_text:
            self.lbl_status.setStyleSheet("color: #ef4444; font-weight: bold; margin-bottom: 10px;")
        else:
            self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold; margin-bottom: 10px;")
            
        lay_db.addWidget(self.lbl_status)

        hbox_btns = QHBoxLayout()
        btn_load = QPushButton("📂 Carregar Banco")
        btn_load.setStyleSheet("background-color: #3b82f6; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        btn_load.clicked.connect(self.acao_carregar)
        
        btn_new = QPushButton("✨ Criar Novo")
        btn_new.setStyleSheet("background-color: #10b981; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        btn_new.clicked.connect(self.acao_novo)
        
        hbox_btns.addWidget(btn_load)
        hbox_btns.addWidget(btn_new)
        lay_db.addLayout(hbox_btns)
        layout.addWidget(gb_db)

        # === SEÇÃO APARÊNCIA ===
        gb_theme = QGroupBox("Aparência")
        lay_theme = QHBoxLayout(gb_theme)
        
        self.rb_claro = QRadioButton("Modo Claro")
        self.rb_escuro = QRadioButton("Modo Escuro")
        
        # Grupo lógico
        self.bg_theme = QButtonGroup(self)
        self.bg_theme.addButton(self.rb_claro, 1)
        self.bg_theme.addButton(self.rb_escuro, 2)
        
        # Define seleção atual
        current_theme = self.parent_window.settings.value("theme", "light")
        if current_theme == "dark":
            self.rb_escuro.setChecked(True)
        else:
            self.rb_claro.setChecked(True)
            
        self.bg_theme.idClicked.connect(self.trocar_tema)
        
        lay_theme.addWidget(self.rb_claro)
        lay_theme.addWidget(self.rb_escuro)
        layout.addWidget(gb_theme)

        # === RODAPÉ ===
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
        btn_fechar.setStyleSheet("padding: 8px; margin-top: 10px;")
        layout.addWidget(btn_fechar)

    def acao_carregar(self):
        self.parent_window.abrir_selecao_arquivo()
        self.lbl_status.setText(self.parent_window.lbl_status_db.text()) # Atualiza label local
        if "Ativo" in self.lbl_status.text():
             self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold; margin-bottom: 10px;")

    def acao_novo(self):
        self.parent_window.criar_novo_arquivo()
        self.lbl_status.setText(self.parent_window.lbl_status_db.text()) # Atualiza label local
        if "Ativo" in self.lbl_status.text():
             self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold; margin-bottom: 10px;")

    def trocar_tema(self, id):
        modo = "dark" if id == 2 else "light"
        self.parent_window.aplicar_tema(modo)

class DatabaseHandler:
    def __init__(self, db_path):
        # Conexão direta com o caminho fornecido pelo usuário via GUI
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.criar_tabelas()
        self.migrar_dados_vazios()

    def reprocessar_dados_existentes(self):
        self.cursor.execute("SELECT visita_id, conteudo FROM detalhes_visitas")
        registros = self.cursor.fetchall()
        if registros:
            for vid, conteudo in registros:
                nome, cpf, horario = self.extrair_dados(conteudo)
                self.cursor.execute("UPDATE detalhes_visitas SET nome = ?, cpf = ?, horario = ? WHERE visita_id = ?", (nome, cpf, horario, vid))
            self.conn.commit()

    def migrar_dados_vazios(self):
        self.cursor.execute("SELECT visita_id, conteudo FROM detalhes_visitas WHERE nome IS NULL OR cpf IS NULL OR horario IS NULL")
        vazios = self.cursor.fetchall()
        if vazios:
            for vid, conteudo in vazios:
                nome, cpf, horario = self.extrair_dados(conteudo)
                self.cursor.execute("UPDATE detalhes_visitas SET nome = ?, cpf = ?, horario = ? WHERE visita_id = ?", (nome, cpf, horario, vid))
            self.conn.commit()

    def criar_tabelas(self):
        self.cursor.execute("PRAGMA user_version")
        versao = self.cursor.fetchone()[0]

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS detalhes_visitas (
                visita_id INTEGER PRIMARY KEY,
                nome TEXT,
                cpf TEXT,
                horario TEXT,
                conteudo TEXT,
                url TEXT,
                data_captura TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.cursor.execute("PRAGMA table_info(detalhes_visitas)")
        columns = [col[1] for col in self.cursor.fetchall()]
        if 'nome' not in columns:
            self.cursor.execute("ALTER TABLE detalhes_visitas ADD COLUMN nome TEXT")
        if 'cpf' not in columns:
            self.cursor.execute("ALTER TABLE detalhes_visitas ADD COLUMN cpf TEXT")
        if 'horario' not in columns:
            self.cursor.execute("ALTER TABLE detalhes_visitas ADD COLUMN horario TEXT")

        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_nome ON detalhes_visitas(nome)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_cpf ON detalhes_visitas(cpf)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_horario ON detalhes_visitas(horario)")

        if versao < 1:
            self.reprocessar_dados_existentes()
            self.cursor.execute("PRAGMA user_version = 1")
        self.conn.commit()

    def salvar_visita(self, visita_id, nome, cpf, horario, conteudo, url):
        try:
            self.cursor.execute('INSERT OR REPLACE INTO detalhes_visitas (visita_id, nome, cpf, horario, conteudo, url) VALUES (?, ?, ?, ?, ?, ?)',
                               (visita_id, nome, cpf, horario, conteudo, url))
            self.conn.commit()
            return True
        except Exception:
            return False

    def buscar_por_filtro(self, termos):
        if not termos: return []
        query = "SELECT visita_id, nome, cpf, horario FROM detalhes_visitas WHERE "
        conditions = []
        params = []
        for t in termos:
            conditions.append("(nome LIKE ? OR cpf LIKE ?)")
            params.extend([f"%{t}%", f"%{t}%"])
        query += " AND ".join(conditions)
        query += " ORDER BY visita_id DESC LIMIT 50"
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def get_maior_id_salvo(self):
        try:
            self.cursor.execute("SELECT MAX(visita_id) FROM detalhes_visitas")
            res = self.cursor.fetchone()
            maior_id = res[0] if res[0] else 0
            return maior_id
        except Exception as e:
            print(f"❌ Erro ao ler maior ID: {e}")
            return 0

    @staticmethod
    def extrair_dados(conteudo):
        if not conteudo:
            return "Desconhecido", "N/A", "N/A"
        reg_nome = r"Visitante:\s*([\w\.\s\-]+)"
        reg_cpf = r"(\d{3}\.\d{3}\.\d{3}-\d{2})"
        reg_horario = r"Horário:\s*(\d{2}/\d{2}/\d{4})\s+\d{2}:\d{2}\s*-\s*(\d{2}/\d{2}/\d{4})\s+\d{2}:\d{2}"
        m_nome = re.search(reg_nome, conteudo, re.IGNORECASE)
        m_cpf = re.search(reg_cpf, conteudo)
        m_horario = re.search(reg_horario, conteudo)
        raw_nome = m_nome.group(1).strip() if m_nome else "Desconhecido"
        cpf = m_cpf.group(1) if m_cpf else "N/A"
        horario = f"{m_horario.group(1)} - {m_horario.group(2)}" if m_horario else "N/A"
        if cpf != "N/A" and cpf in raw_nome:
            raw_nome = raw_nome.replace(cpf, "")
        clean_nome = raw_nome.split("Telefone")[0].split("CPF")[0].split("Celular")[0].split("Horário")[0].strip(" -")
        if not clean_nome: clean_nome = "Desconhecido"
        return clean_nome, cpf, horario

class SmartPortariaScanner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Monitor Portaria - Gestão de Dados")
        self.resize(1400, 900)
        
        # Gerenciador de configurações persistentes
        self.settings = QSettings("PortariaApps", "MonitorVisitas")
        
        # INICIALIZA SEM BANCO DE DADOS
        self.db = None
        self.id_atual = 1
        self.rodando = True
        
        self.timer_retry = QTimer()
        self.timer_retry.setSingleShot(True)
        self.timer_retry.timeout.connect(self.carregar_url_id)

        self.profile_anonimo = QWebEngineProfile(self) 
        self.profile_anonimo.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        self.setup_ui()
        self.configurar_navegadores()

        # Carrega e aplica tema salvo
        saved_theme = self.settings.value("theme", "light")
        self.aplicar_tema(saved_theme)

        self.timer_busca = QTimer()
        self.timer_busca.setSingleShot(True)
        self.timer_busca.timeout.connect(self.executar_busca_local)
        
        self.add_new_tab(QUrl("https://portaria-global.governarti.com.br/visita/"), "Portaria Virtual", closable=False)
        self.add_new_tab(QUrl("about:blank"), "Guia anônima", closable=False, profile=self.profile_anonimo)
        
        self.tabs.setCurrentIndex(0)
        self.web_stack.setCurrentIndex(0)

        self.txt_live.append(f"--- SISTEMA INICIADO: {datetime.datetime.now().strftime('%H:%M:%S')} ---")
        
        # Tenta carregar automaticamente o último banco usado
        self.carregar_ultimo_banco()

    def setup_ui(self):
        self.central = QWidget()
        self.setCentralWidget(self.central)
        layout = QHBoxLayout(self.central)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- PAINEL ESQUERDO ---
        painel = QWidget()
        painel.setFixedWidth(450)
        lat = QVBoxLayout(painel)
        lat.setSpacing(10)

        # === CABEÇALHO DO PAINEL COM BOTÃO DE ENGRENAGEM ===
        header_layout = QHBoxLayout()
        lbl_titulo = QLabel("Painel de Controle")
        lbl_titulo.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.btn_config = QPushButton("⚙️")
        self.btn_config.setToolTip("Abrir Configurações")
        self.btn_config.setFixedSize(32, 32)
        # Estilo do botão será gerido pelo tema global
        self.btn_config.clicked.connect(self.abrir_configuracoes)

        header_layout.addWidget(lbl_titulo)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_config)
        lat.addLayout(header_layout)

        # Pequeno status do banco no painel
        self.lbl_status_db = QLabel("⚠️ Nenhum banco carregado")
        self.lbl_status_db.setStyleSheet("color: #ef4444; font-weight: bold; margin-bottom: 5px; font-size: 11px;")
        self.lbl_status_db.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lat.addWidget(self.lbl_status_db)

        # === GRUPO BUSCA NO BANCO ===
        group_busca = QGroupBox("BUSCA NO BANCO DE DADOS")
        layout_busca = QVBoxLayout(group_busca)
        
        busca_input_layout = QHBoxLayout()
        busca_input_layout.setContentsMargins(0, 0, 0, 0)
        busca_input_layout.setSpacing(5)

        self.input_busca = QLineEdit()
        self.input_busca.setPlaceholderText("Digite para buscar...")
        self.input_busca.textChanged.connect(self.realizar_busca_local)
        
        self.btn_limpar_busca = QPushButton("✖")
        self.btn_limpar_busca.setFixedWidth(30)
        self.btn_limpar_busca.clicked.connect(self.input_busca.clear)

        busca_input_layout.addWidget(self.input_busca)
        busca_input_layout.addWidget(self.btn_limpar_busca)
        
        layout_busca.addLayout(busca_input_layout)
        
        self.txt_res_busca = QTextBrowser()
        self.txt_res_busca.setOpenExternalLinks(False)
        self.txt_res_busca.setMaximumHeight(400)
        # O estilo base transparente é bom, mas vamos deixar o tema controlar a cor do texto
        self.txt_res_busca.setStyleSheet("border: none; background: transparent;")
        self.txt_res_busca.anchorClicked.connect(self.abrir_link_resultado)
        layout_busca.addWidget(self.txt_res_busca)
        lat.addWidget(group_busca)

        # === GRUPO LOG ===
        group_live = QGroupBox("LOG DO SISTEMA")
        layout_live = QVBoxLayout(group_live)
        self.txt_live = QTextEdit()
        self.txt_live.setReadOnly(True)
        # Fonte monospace fixa, mas cores geridas pelo tema
        self.txt_live.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        layout_live.addWidget(self.txt_live)
        lat.addWidget(group_live)

        # === GRUPO EXTRATOR DE LINK ===
        group_qr = QGroupBox("EXTRATOR DE LINK")
        layout_qr = QVBoxLayout(group_qr)
        self.txt_qr_input = QTextEdit()
        self.txt_qr_input.setPlaceholderText("Cole a mensagem aqui para extrair o link...")
        self.txt_qr_input.setMaximumHeight(100)
        layout_qr.addWidget(self.txt_qr_input)

        btns_layout = QHBoxLayout()
        self.btn_open_anon = QPushButton("Abrir na Guia Anônima")
        self.btn_open_anon.clicked.connect(self.abrir_qr_na_anonima)

        self.btn_gen_qr = QPushButton("Gerar QR Code")
        self.btn_gen_qr.clicked.connect(self.mostrar_qr_code)

        self.btn_clear_qr = QPushButton("Apagar")
        self.btn_clear_qr.setFixedWidth(70)
        self.btn_clear_qr.clicked.connect(self.txt_qr_input.clear)

        btns_layout.addWidget(self.btn_open_anon)
        btns_layout.addWidget(self.btn_gen_qr)
        btns_layout.addWidget(self.btn_clear_qr)
        layout_qr.addLayout(btns_layout)
        lat.addWidget(group_qr)

        # --- NAVEGADOR PRINCIPAL ---
        container_web = QWidget()
        layout_web = QVBoxLayout(container_web)
        layout_web.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.btn_back = QPushButton("←")
        self.btn_back.setFixedWidth(30)
        self.btn_forward = QPushButton("→")
        self.btn_forward.setFixedWidth(30)
        self.btn_reload = QPushButton("↻")
        self.btn_reload.setFixedWidth(30)

        self.btn_back.clicked.connect(self.navegar_voltar)
        self.btn_forward.clicked.connect(self.navegar_avancar)
        self.btn_reload.clicked.connect(self.recarregar_pagina)
        
        self.btn_unlock = QPushButton("Destravar")
        self.btn_unlock.clicked.connect(self.executar_desbloqueio)

        self.btn_home = QPushButton("🏠")
        self.btn_home.setFixedWidth(60)
        self.btn_home.setStyleSheet("font-size: 18px; padding-bottom: 3px;")
        self.btn_home.clicked.connect(self.ir_para_home)

        self.address_bar = QLineEdit()
        self.address_bar.setPlaceholderText("Introduza o URL...")
        self.address_bar.returnPressed.connect(self.ir_para_url)

        self.tabs = QTabBar()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        # Estilos do TabBar agora serão definidos no aplicar_tema
        self.tabs.tabCloseRequested.connect(self.fechar_aba)
        self.tabs.currentChanged.connect(self.mudar_aba)

        self.btn_abrir_camera = QPushButton("📷")
        self.btn_abrir_camera.setToolTip("Abrir Câmera")
        self.btn_abrir_camera.setFixedWidth(40)
        self.btn_abrir_camera.clicked.connect(self.abrir_camera)

        toolbar.addWidget(self.btn_back)
        toolbar.addWidget(self.btn_forward)
        toolbar.addWidget(self.btn_reload)
        toolbar.addWidget(self.btn_unlock)
        toolbar.addWidget(self.btn_home)
        toolbar.addWidget(self.address_bar)
        toolbar.addWidget(self.tabs)
        toolbar.addWidget(self.btn_abrir_camera)
        layout_web.addLayout(toolbar)

        self.web_stack = QStackedWidget()
        layout_web.addWidget(self.web_stack)

        self.view_worker = QWebEngineView()
        self.view_worker.setVisible(False)
        self.view_worker.loadFinished.connect(self.on_worker_load_finished)
        
        splitter.addWidget(painel)
        splitter.addWidget(container_web)
        layout.addWidget(splitter)

    # === LÓGICA DE TEMAS ===
    def aplicar_tema(self, modo):
        self.settings.setValue("theme", modo)
        
        if modo == "dark":
            # Estilo ESCURO
            style = """
                QMainWindow, QWidget { background-color: #0f172a; color: #e2e8f0; }
                QLineEdit { background-color: #1e293b; color: #e2e8f0; border: 1px solid #475569; padding: 6px; border-radius: 4px; }
                QTextEdit { background-color: #1e293b; color: #e2e8f0; border: 1px solid #475569; border-radius: 4px; }
                QGroupBox { border: 1px solid #475569; border-radius: 6px; margin-top: 10px; font-weight: bold; color: #94a3b8; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
                QLabel { color: #e2e8f0; }
                QPushButton { background-color: #334155; color: white; border: 1px solid #475569; border-radius: 4px; padding: 6px; }
                QPushButton:hover { background-color: #475569; }
                QTabBar::tab { background: #1e293b; color: #94a3b8; border: 1px solid #475569; padding: 8px 30px 8px 12px; border-radius: 4px; margin-right: 4px; }
                QTabBar::tab:selected { background: #2563eb; color: white; border-color: #2563eb; }
                QSplitter::handle { background-color: #475569; }
            """
            # Cores específicas de botões funcionais
            btn_unlock_style = "background-color: #d97706; color: white; font-weight: bold; border-radius: 4px; padding: 5px 10px;"
            btn_anon_style = "background-color: #475569; color: white; padding: 8px; border-radius: 4px;"
            btn_qr_style = "background-color: #2563eb; color: white; padding: 8px; border-radius: 4px; font-weight: bold;"
            btn_clear_style = "background-color: #ef4444; color: white; padding: 8px; border-radius: 4px; font-weight: bold;"
            live_log_style = "background: #1e293b; color: #4ade80; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #475569;"

        else:
            # Estilo CLARO (Padrão)
            style = """
                QMainWindow, QWidget { background-color: #f8fafc; color: #1e293b; }
                QLineEdit { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; padding: 6px; border-radius: 4px; }
                QTextEdit { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; }
                QGroupBox { border: 1px solid #94a3b8; border-radius: 6px; margin-top: 10px; font-weight: bold; color: #1e293b; }
                QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; }
                QLabel { color: #1e293b; }
                QPushButton { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px; }
                QPushButton:hover { background-color: #e2e8f0; }
                QTabBar::tab { background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; padding: 8px 30px 8px 12px; border-radius: 4px; margin-right: 4px; }
                QTabBar::tab:selected { background: #2563eb; color: white; border-color: #2563eb; }
                QSplitter::handle { background-color: #cbd5e1; }
            """
            # Cores específicas
            btn_unlock_style = "background-color: #f59e0b; color: white; font-weight: bold; border-radius: 4px; padding: 5px 10px;"
            btn_anon_style = "background-color: #334155; color: white; padding: 8px; border-radius: 4px;"
            btn_qr_style = "background-color: #2563eb; color: white; padding: 8px; border-radius: 4px; font-weight: bold;"
            btn_clear_style = "background-color: #ef4444; color: white; padding: 8px; border-radius: 4px; font-weight: bold;"
            live_log_style = "background: #1e293b; color: #4ade80; font-family: Consolas, monospace; font-size: 12px;"

        self.setStyleSheet(style)
        
        # Reaplica estilos específicos que não devem ser sobrescritos pelo genérico
        self.btn_unlock.setStyleSheet(btn_unlock_style)
        self.btn_open_anon.setStyleSheet(btn_anon_style)
        self.btn_gen_qr.setStyleSheet(btn_qr_style)
        self.btn_abrir_camera.setStyleSheet(btn_qr_style)
        self.btn_clear_qr.setStyleSheet(btn_clear_style)
        self.btn_limpar_busca.setStyleSheet(f"background-color: {'#334155' if modo=='dark' else '#e2e8f0'}; color: {'#e2e8f0' if modo=='dark' else '#64748b'}; border: none; border-radius: 4px; font-weight: bold;")
        self.txt_live.setStyleSheet(live_log_style)
        self.btn_home.setStyleSheet("font-size: 18px; padding-bottom: 3px;" + ("color: white;" if modo == "dark" else ""))
        
        # Ajusta botão de configuração para parecer com o tema
        btn_conf_color = "#334155" if modo == "dark" else "#f1f5f9"
        btn_conf_border = "#475569" if modo == "dark" else "#cbd5e1"
        self.btn_config.setStyleSheet(f"""
            QPushButton {{ background-color: {btn_conf_color}; border: 1px solid {btn_conf_border}; border-radius: 6px; font-size: 18px; }}
            QPushButton:hover {{ border-color: #94a3b8; }}
        """)

    # === MÉTODOS DE CONTROLE DO BANCO DE DADOS ===
    def abrir_configuracoes(self):
        """Abre o diálogo de configurações central"""
        dlg = ConfigDialog(self)
        dlg.exec()

    def abrir_selecao_arquivo(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Selecionar Banco de Dados", "", "SQLite Database (*.db);;Todos os Arquivos (*)")
        if fname:
            self.conectar_banco(fname)

    def criar_novo_arquivo(self):
        fname, _ = QFileDialog.getSaveFileName(self, "Salvar Novo Banco de Dados", "", "SQLite Database (*.db)")
        if fname:
            self.conectar_banco(fname)

    def carregar_ultimo_banco(self):
        """Verifica se existe um banco salvo nas configurações e tenta carregar"""
        last_db = self.settings.value("last_db_path")
        if last_db and os.path.exists(last_db):
            self.txt_live.append(f"📁 Encontrado banco salvo: {last_db}")
            self.conectar_banco(last_db)
        else:
            self.txt_live.append("⚠️ Nenhum banco anterior encontrado. Configure nas opções.")
            # self.abrir_configuracoes() # Opcional: abrir auto

    def conectar_banco(self, path):
        try:
            self.db = DatabaseHandler(path)
            nome_arq = os.path.basename(path)
            self.lbl_status_db.setText(f"✅ Ativo: {nome_arq}")
            self.lbl_status_db.setStyleSheet("color: #10b981; font-weight: bold; margin-bottom: 5px; font-size: 11px;")
            
            # Salva o caminho para a próxima sessão
            self.settings.setValue("last_db_path", path)
            
            self.txt_live.append(f"--- BANCO CONECTADO: {path} ---")
            self.carregar_ultimo_id()
            self.carregar_url_id()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro de Conexão", f"Falha ao conectar ao banco de dados:\n{e}")
            self.settings.remove("last_db_path")

    # === MÉTODOS DE NAVEGAÇÃO ===
    def navegar_voltar(self):
        view = self.web_stack.currentWidget()
        if view: view.back()

    def navegar_avancar(self):
        view = self.web_stack.currentWidget()
        if view: view.forward()

    def recarregar_pagina(self):
        view = self.web_stack.currentWidget()
        if view: view.reload()

    def add_new_tab(self, qurl, title, closable=True, profile=None):
        view = QWebEngineView()
        target_profile = profile if profile else QWebEngineProfile.defaultProfile()
        page = CustomWebPage(target_profile, view, self)
        view.setPage(page)
        
        view.urlChanged.connect(lambda q: self.atualizar_barra_endereco(q, view))
        view.titleChanged.connect(lambda t: self.atualizar_titulo_aba(t, view))
        view.loadFinished.connect(lambda ok: self.on_tab_load_finished(ok, view))
        
        idx = self.web_stack.addWidget(view)
        tab_idx = self.tabs.addTab(title)
        if not closable: 
            self.tabs.setTabButton(tab_idx, QTabBar.ButtonPosition.RightSide, None)
            
        if qurl and not qurl.isEmpty(): 
            view.setUrl(qurl)
            
        self.tabs.setCurrentIndex(tab_idx)
        self.web_stack.setCurrentIndex(idx)
        return view

    def executar_desbloqueio(self):
        view = self.web_stack.currentWidget()
        if not view: return
        js_hack = """
        (function() {
            var disabledEls = document.querySelectorAll('*[disabled], .disabled, .blocked, .locked, [aria-disabled="true"]');
            disabledEls.forEach(el => {
                el.removeAttribute('disabled');
                el.classList.remove('disabled', 'blocked', 'locked');
                el.setAttribute('aria-disabled', 'false');
                el.style.pointerEvents = 'auto';
                el.style.opacity = '1';
                el.style.cursor = 'pointer';
            });
        })();
        """
        view.page().runJavaScript(js_hack)

    def ir_para_url(self):
        url_texto = self.address_bar.text().strip()
        if not url_texto: return
        if url_texto != "about:blank" and not url_texto.startswith("http") and not url_texto.startswith("about:"):
            url_texto = "https://" + url_texto
        view = self.web_stack.currentWidget()
        if view: view.setUrl(QUrl(url_texto))

    def ir_para_home(self):
        view = self.web_stack.currentWidget()
        if view:
            if view.page().profile() == self.profile_anonimo: view.setUrl(QUrl("https://www.google.com"))
            else: view.setUrl(QUrl("https://portaria-global.governarti.com.br/visita/"))

    def mudar_aba(self, index):
        if index >= 0:
            self.web_stack.setCurrentIndex(index)
            view = self.web_stack.currentWidget()
            if view:
                url_str = view.url().toString()
                self.address_bar.setText("" if url_str == "about:blank" else url_str)

    def fechar_aba(self, index):
        titulo = self.tabs.tabText(index)
        if "Portaria Virtual" in titulo or "anônima" in titulo.lower(): return
        widget = self.web_stack.widget(index)
        if widget:
            self.web_stack.removeWidget(widget)
            widget.deleteLater()
        self.tabs.removeTab(index)

    def atualizar_titulo_aba(self, titulo, view):
        index = self.web_stack.indexOf(view)
        if index != -1:
            current_text = self.tabs.tabText(index)
            if "Portaria Virtual" in current_text or "anônima" in current_text.lower(): return
            display_title = (titulo[:12] + "...") if len(titulo) > 12 else titulo
            self.tabs.setTabText(index, display_title)

    def atualizar_barra_endereco(self, qurl, view):
        if view == self.web_stack.currentWidget():
            url_str = qurl.toString()
            self.address_bar.setText("" if url_str == "about:blank" else url_str)

    def configurar_navegadores(self):
        s_worker = self.view_worker.settings()
        s_worker.setAttribute(QWebEngineSettings.WebAttribute.AutoLoadImages, False)
        s_worker.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

    def carregar_ultimo_id(self):
        if not self.db: return
        maior = self.db.get_maior_id_salvo()
        if maior > 0: 
            self.id_atual = maior + 1
            self.txt_live.append(f"🔄 Retomando captura a partir do ID: {self.id_atual}")
        else:
            self.txt_live.append("✨ Banco vazio/novo. Começando do ID 1.")
            self.id_atual = 1

    def carregar_url_id(self):
        if not self.rodando or not self.db: return
        url = f"https://portaria-global.governarti.com.br/visita/{self.id_atual}/detalhes?t={datetime.datetime.now().timestamp()}"
        self.view_worker.setUrl(QUrl(url))

    def injetar_login(self, browser_view):
        if browser_view.page().profile() == self.profile_anonimo: return
        url_atual = browser_view.url().toString()
        if "portaria-global.governarti.com.br/login" in url_atual:
            js_login = "document.querySelectorAll('input').forEach(i => { if(i.type=='text') i.value='armando.junior'; if(i.type=='password') i.value='armandocampos.1'; });"
            browser_view.page().runJavaScript(js_login)

    def on_tab_load_finished(self, ok, view):
        self.injetar_login(view)

    def on_worker_load_finished(self, ok):
        self.injetar_login(self.view_worker)
        if self.rodando and self.db: QTimer.singleShot(800, self.extrair_e_validar)

    def extrair_e_validar(self):
        self.view_worker.page().runJavaScript("document.body.innerText;", self.callback_validacao)

    def callback_validacao(self, conteudo):
        if not self.rodando or not self.db: return
        if not conteudo or "entrar" in conteudo.lower()[:300]:
            self.timer_retry.start(3000)
            return

        nome_str, cpf_str, horario_str = self.db.extrair_dados(conteudo)
        dados_encontrados = (nome_str != "Desconhecido" or cpf_str != "N/A") and "não encontrada" not in conteudo.lower()

        if dados_encontrados:
            self.db.salvar_visita(self.id_atual, nome_str, cpf_str, horario_str, conteudo, self.view_worker.url().toString())
            self.txt_live.append(f"ID {self.id_atual} registrado: {nome_str}")
            self.id_atual += 1
            QTimer.singleShot(500, self.carregar_url_id)
        else:
            self.timer_retry.start(10000)

    def realizar_busca_local(self):
        if not self.db: return
        self.timer_busca.start(300)

    def executar_busca_local(self):
        if not self.db: return
        termo = self.input_busca.text().strip().lower()
        if not termo: 
            self.txt_res_busca.clear()
            return
        termos = termo.split()
        dados = self.db.buscar_por_filtro(termos)
        html = ""
        hoje = datetime.date.today()
        # Define cor do texto baseada no tema
        text_color = "#e2e8f0" if self.settings.value("theme") == "dark" else "#1e293b"
        card_bg = "#1e293b" if self.settings.value("theme") == "dark" else "#ffffff"
        border_color = "#475569" if self.settings.value("theme") == "dark" else "#cbd5e1"
        
        for vid, nome, cpf, horario in dados:
            cor_validade = "green"
            if horario and horario != "N/A":
                try:
                    partes = horario.split(" - ")
                    if len(partes) == 2:
                        data_fim = datetime.datetime.strptime(partes[1].strip(), "%d/%m/%Y").date()
                        if data_fim < hoje: cor_validade = "red"
                except: pass
            
            html += f"""
            <a href="{vid}" style="text-decoration: none;">
                <div style='background-color: {card_bg}; border: 1px solid {border_color}; border-bottom: 3px solid {border_color}; border-radius: 8px; padding: 12px; margin-bottom: 8px;'>
                    <div style='color: {text_color}; font-size: 14px;'>
                        <b style='color: #2563eb;'>ID {vid}:</b> {nome}<br>
                        <span style='color: #64748b; font-size: 12px;'>CPF / ID: {cpf}</span><br>
                        <span style='color: #64748b; font-size: 12px;'><b>Validade:</b> <span style='color: {cor_validade}; font-weight: bold;'>{horario}</span></span>
                    </div>
                </div>
            </a>
            """
        self.txt_res_busca.setHtml(html)

    def abrir_link_resultado(self, url_qurl):
        visita_id = url_qurl.toString()
        link_final = f"https://portaria-global.governarti.com.br/visita/{visita_id}/detalhes"
        for i in range(self.tabs.count()):
            if "Portaria Virtual" in self.tabs.tabText(i):
                self.tabs.setCurrentIndex(i)
                view = self.web_stack.widget(i)
                if view: view.setUrl(QUrl(link_final))
                return
        self.add_new_tab(QUrl(link_final), f"ID {visita_id}")

    def extrair_url_qr(self):
        texto = self.txt_qr_input.toPlainText()
        match = re.search(r'https?://[^\s]+', texto)
        if match: return match.group(0).rstrip('.')
        return None

    def abrir_qr_na_anonima(self):
        url = self.extrair_url_qr()
        if not url:
            QMessageBox.warning(self, "Aviso", "Nenhuma URL encontrada na mensagem.")
            return
        for i in range(self.tabs.count()):
            if "anônima" in self.tabs.tabText(i).lower():
                self.tabs.setCurrentIndex(i)
                view = self.web_stack.widget(i)
                if view: view.setUrl(QUrl(url))
                return
        self.add_new_tab(QUrl(url), "Guia anônima", closable=False, profile=self.profile_anonimo)

    def mostrar_qr_code(self):
        url = self.extrair_url_qr()
        if not url:
            QMessageBox.warning(self, "Aviso", "Nenhuma URL encontrada na mensagem.")
            return
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(url)
            qr.make(fit=True)
            img_pil = qr.make_image(fill_color="black", back_color="white")
            actual_image = img_pil._img
            qimg = ImageQt(actual_image)
            pixmap = QPixmap.fromImage(qimg)
            dlg = QRDialog(pixmap, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao gerar QR Code: {str(e)}")

    def abrir_camera(self):
        """Abre o diálogo de captura de foto"""
        cameras = QMediaDevices.videoInputs()
        if not cameras:
            QMessageBox.warning(self, "Câmera não encontrada", "Nenhum dispositivo de vídeo foi detectado no sistema.")
            return

        # Tenta evitar a câmera integrada
        camera_selecionada = cameras[0]
        if len(cameras) > 1:
            # Primeiro procura por câmeras que pareçam externas
            for cam in cameras:
                desc = cam.description().lower()
                if "usb" in desc or "external" in desc:
                    camera_selecionada = cam
                    break

            # Se não achou por palavra-chave positiva, tenta excluir as que parecem integradas
            if camera_selecionada == cameras[0]:
                for cam in cameras:
                    desc = cam.description().lower()
                    if "integrated" not in desc and "built-in" not in desc and "notebook" not in desc:
                        camera_selecionada = cam
                        break

        dlg = CameraDialog(self, camera_device=camera_selecionada)
        dlg.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SmartPortariaScanner()
    win.show()
    sys.exit(app.exec())
