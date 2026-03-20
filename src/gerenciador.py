# -*- coding: utf-8 -*-

import sys
import subprocess
import os
import json
from datetime import datetime
import logging
import asyncio
import discord

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTextEdit, QSplitter, QTimeEdit,
    QDialog, QDialogButtonBox, QLineEdit, QListWidget, QMessageBox
)
from PyQt5.QtGui import QFont, QCursor
from PyQt5.QtCore import Qt, QTimer, QTime, QThread, pyqtSignal

# =============================================================================
# CONFIGURAÇÃO PRINCIPAL DOS BOTS
# =============================================================================
def load_bots_from_settings():
    bots_dict = {}
    settings_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding='utf-8') as f:
                data = json.load(f)
                for b in data.get("bots", {}).keys():
                    bots_dict[b] = {"process": None}
        except Exception as e:
            print(f"Erro ao carregar settings.json no gerenciador: {e}")
    else:
        # Fallback if settings.json is somehow missing
        default_bots = ["Híbrida 1", "Híbrida 2", "Híbrida 3", "Híbrida 4", "Híbrida 5", "PGM"]
        for b in default_bots:
            bots_dict[b] = {"process": None}
    return bots_dict

bots = load_bots_from_settings()

WORKER_EXE = "bot_worker.exe"
WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "bot_worker.py")

def get_worker_command(bot_name):
    """Retorna a lista de comandos baseada na existência do executável compilado."""
    if os.path.exists(WORKER_EXE):
        return [WORKER_EXE, "--bot", bot_name]
    else:
        return [sys.executable, WORKER_SCRIPT, "--bot", bot_name]

# =============================================================================
# COMPONENTES DE UI PERSONALIZADOS
# =============================================================================

class StatusDot(QLabel):
    def __init__(self):
        super().__init__()
        self.setFixedSize(8, 8)
        self.set_offline()

    def set_online(self):
        self.setStyleSheet("background-color: #00D26A; border-radius: 4px;")

    def set_offline(self):
        self.setStyleSheet("background-color: #FF5F56; border-radius: 4px;")

    def set_error(self):
        self.setStyleSheet("background-color: #FFBD2E; border-radius: 4px;")

class ModernButton(QPushButton):
    def __init__(self, text, button_type="primary"):
        super().__init__(text)
        self.setMinimumHeight(36)
        self.setFont(QFont("Inter", 10, QFont.Medium))
        self.setCursor(QCursor(Qt.PointingHandCursor))

        styles = {
            "primary": ("#007AFF", "#0056CC"),
            "success": ("#28A745", "#1E7E34"),
            "danger": ("#DC3545", "#C82333"),
            "secondary": ("#6C757D", "#5A6268"),
        }
        bg_color, hover_color = styles.get(button_type, styles["primary"])

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
        """)


class BotCard(QFrame):
    def __init__(self, bot_name, start_callback, stop_callback):
        super().__init__()
        self.bot_name = bot_name
        self.start_callback = start_callback
        self.stop_callback = stop_callback

        self.setFixedSize(280, 120)
        self.setStyleSheet("""
            QFrame {
                background-color: #1C1C1E;
                border: 1px solid #2C2C2E;
                border-radius: 12px;
            }
            QFrame:hover {
                border: 1px solid #007AFF;
            }
        """)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        self.status_dot = StatusDot()
        name_label = QLabel(self.bot_name)
        name_label.setFont(QFont("Inter", 12, QFont.Medium))
        name_label.setStyleSheet("color: #FFFFFF; font-weight: 500;")
        self.status_label = QLabel("Offline")
        self.status_label.setFont(QFont("Inter", 10))
        self.status_label.setStyleSheet("color: #8E8E93;")

        header_layout.addWidget(self.status_dot)
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)

        buttons_layout = QHBoxLayout()
        self.btn_start = ModernButton("Iniciar", "success")
        self.btn_start.clicked.connect(lambda: self.start_callback(self.bot_name))
        self.btn_stop = ModernButton("Parar", "danger")
        self.btn_stop.clicked.connect(lambda: self.stop_callback(self.bot_name))
        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_stop)

        layout.addLayout(header_layout)
        layout.addStretch()
        layout.addLayout(buttons_layout)

    def update_status(self, status, text):
        if status == "online":
            self.status_dot.set_online()
        elif status == "offline":
            self.status_dot.set_offline()
        elif status == "error":
            self.status_dot.set_error()
        self.status_label.setText(text)

# =============================================================================
# LISTENER DO DISCORD PARA N8N (COMANDOS)
# =============================================================================
class DiscordListenerThread(QThread):
    command_received = pyqtSignal(str)

    def __init__(self, token, channel_id=None):
        super().__init__()
        self.token = token
        self.channel_id = channel_id
        self.loop = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            print(f"[DiscordListener] Conectado como {client.user} para escutar comandos N8N.")

        @client.event
        async def on_message(message):
            if self.channel_id and message.channel.id != self.channel_id:
                return

            content = message.content.strip().lower()
            if content.startswith("/"):
                # Emite o sinal com o comando recebido, o PyQt garante processamento seguro na main thread
                self.command_received.emit(content)

        try:
            client.run(self.token)
        except Exception as e:
            print(f"[DiscordListener] Erro ao inciar o listener do Discord: {e}")

class BotManager(QWidget):
    SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "schedules.json")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerenciador de Bots Vanguarda")
        self.setFixedSize(1000, 700)
        self.setStyleSheet("""
            QWidget {
                background-color: #000000;
                color: #FFFFFF;
                font-family: 'Inter', 'Segoe UI', sans-serif;
            }
        """)

        self.scheduled_times = self.load_schedules_from_disk()

        self.setup_ui()

        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_scheduled_tasks)
        self.scheduler_timer.start(60000)

        self.log("Sistema inicializado com sucesso. Preparado para a migração unificada.")
        self.log(f"{len(self.scheduled_times)} agendamento(s) carregado(s).")

        # Timer checks UI status periodicamente
        self.status_checker = QTimer(self)
        self.status_checker.timeout.connect(self.check_processes_status)
        self.status_checker.start(5000)
        
        # Inicializa o listener do Discord para comandos do N8N
        self.discord_thread = None
        self.init_discord_listener()

    def init_discord_listener(self):
        token = None
        channel_id = None
        settings_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
        
        try:
            with open(settings_path, "r", encoding='utf-8') as f:
                data = json.load(f)
                token = data.get("n8n_bot_token", "")
                
                # Pega o ID do canal para restringir escuta (usa padrão caso não exista campo próprio)
                if "n8n_channel_id" in data:
                    channel_id = data["n8n_channel_id"]
                else:
                    for b_data in data.get("bots", {}).values():
                        if "canal_texto_id" in b_data:
                            channel_id = b_data["canal_texto_id"]
                            break
        except Exception as e:
            self.log(f"Erro ao ler settings.json para config do Discord: {e}")
        
        if token:
            self.discord_thread = DiscordListenerThread(token, channel_id)
            self.discord_thread.command_received.connect(self.handle_discord_command)
            self.discord_thread.start()
            self.log("Listener do Discord (N8N Bot) iniciado com sucesso.")
        else:
            self.log("Alerta: Nenhum token de N8N bot encontrado ('n8n_bot_token' vazio em settings.json). Listener inativo.")

    def handle_discord_command(self, command):
        self.log(f"Comando N8N recebido via Discord: {command}")
        if command == "/reiniciarhib":
            self.log("N8N: Reiniciando TODAS as híbridas...")
            self.stop_all_bots()
            QTimer.singleShot(3000, self.start_all_bots)
        elif command == "/rhib1":
            self.restart_specific_bot("Híbrida 1")
        elif command == "/rhib2":
            self.restart_specific_bot("Híbrida 2")
        elif command == "/rhib3":
            self.restart_specific_bot("Híbrida 3")
        elif command == "/rhib4":
            self.restart_specific_bot("Híbrida 4")
        elif command == "/rhib5":
            self.restart_specific_bot("Híbrida 5")
        elif command == "/rpgm":
            self.restart_specific_bot("PGM")

    def restart_specific_bot(self, name):
        if name in bots:
            self.log(f"N8N: Reiniciando {name}...")
            self.stop_bot(name)
            QTimer.singleShot(3000, lambda n=name: self.start_bot(n))

    def check_processes_status(self):
        """Verifica se os processos dos bots caíram silenciosamente"""
        for name, info in bots.items():
            proc = info.get("process")
            if proc is not None:
                if proc.poll() is not None: # Processo terminou
                    self.log(f"Alerta: O processo do bot '{name}' terminou inesperadamente com código {proc.returncode}.")
                    info["process"] = None
                    self.bot_cards[name].update_status("error", "Erro/Fechado")
        self.update_status_summary()

    def closeEvent(self, event):
        """Assegura que quando a UI for fechada, todos os bots parem."""
        self.stop_all_bots()
        event.accept()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(24)

        header_layout = QVBoxLayout()
        title = QLabel("Gerenciador de Híbridas Vanguarda")
        title.setFont(QFont("Inter", 24, QFont.Bold))
        subtitle = QLabel("Monitore, gerencie e agende suas instâncias (Versão Unificada).")
        subtitle.setFont(QFont("Inter", 14))
        subtitle.setStyleSheet("color: #8E8E93;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        controls_frame = QFrame()
        controls_frame.setFixedHeight(60)
        controls_frame.setStyleSheet("background-color: #1C1C1E; border: 1px solid #2C2C2E; border-radius: 8px;")
        controls_layout = QHBoxLayout(controls_frame)
        self.btn_start_all = ModernButton("Iniciar Todos", "success")
        self.btn_start_all.clicked.connect(self.start_all_bots)
        self.btn_stop_all = ModernButton("Parar Todos", "danger")
        self.btn_stop_all.clicked.connect(self.stop_all_bots)
        self.btn_schedule = ModernButton("Agendar", "primary")
        self.btn_schedule.clicked.connect(self.open_schedule_dialog)
        self.status_summary = QLabel()
        self.status_summary.setStyleSheet("color: #8E8E93; font-size: 12px;")

        controls_layout.addWidget(self.btn_start_all)
        controls_layout.addWidget(self.btn_stop_all)
        controls_layout.addWidget(self.btn_schedule)
        controls_layout.addStretch()
        controls_layout.addWidget(self.status_summary)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setStyleSheet("QSplitter::handle { background-color: #2C2C2E; width: 1px; }")

        bots_frame = QFrame()
        bots_layout = QVBoxLayout(bots_frame)
        bots_grid_widget = QWidget()
        grid_layout = QGridLayout(bots_grid_widget)
        grid_layout.setSpacing(16)
        self.bot_cards = {}
        row, col = 0, 0
        for bot_name in bots:
            card = BotCard(bot_name, self.start_bot, self.stop_bot)
            self.bot_cards[bot_name] = card
            grid_layout.addWidget(card, row, col)
            col += 1
            if col > 1:
                col = 0
                row += 1
        bots_layout.addWidget(bots_grid_widget)
        bots_layout.addStretch()
        bots_frame.setLayout(bots_layout)

        logs_frame = QFrame()
        logs_layout = QVBoxLayout(logs_frame)
        logs_title = QLabel("Painel Padrão (Logs GUI)")
        logs_title.setFont(QFont("Inter", 16, QFont.Medium))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #0D0D0D; border: 1px solid #2C2C2E; border-radius: 6px;
                color: #00D26A; font-family: 'JetBrains Mono', monospace; font-size: 11px;
            }
        """)
        logs_layout.addWidget(logs_title)
        logs_layout.addWidget(self.log_area)

        content_splitter.addWidget(bots_frame)
        content_splitter.addWidget(logs_frame)
        content_splitter.setSizes([600, 400])

        main_layout.addLayout(header_layout)
        main_layout.addWidget(controls_frame)
        main_layout.addWidget(content_splitter)
        
        self.update_status_summary()

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def start_bot(self, name):
        bot = bots.get(name)
        if bot and bot.get("process") is None:
            try:
                log_dir = "logs"
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)

                # Output logs em modo write, pois o worker tem seu próprio RollingFileHandler
                # Mas para caso ocorra crash no load do script:
                log_file_path = os.path.join(log_dir, f"{name.replace(' ', '_').replace('í', 'i').lower()}_crash.txt")
                log_file = open(log_file_path, "a", encoding='utf-8')

                creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0

                cmd = get_worker_command(name)
                bot["process"] = subprocess.Popen(
                    cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=creation_flags
                )

                self.bot_cards[name].update_status("online", "Executando")
                self.log(f"Bot '{name}' iniciado. ({' '.join(cmd)})")
            except Exception as e:
                self.bot_cards[name].update_status("error", "Erro ao executar")
                self.log(f"ERRO ao iniciar '{name}': {e}")
        else:
            self.log(f"Bot '{name}' já está em execução.")
        self.update_status_summary()

    def stop_bot(self, name):
        bot = bots.get(name)
        if bot and bot.get("process"):
            try:
                bot["process"].terminate()
                # Windows might need a harder kill for subprocesses with ffmpeg
                if sys.platform == 'win32':
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(bot["process"].pid)], capture_output=True)
            except Exception as e:
                self.log(f"Erro ao matar o processo {name}: {e}")
                
            bot["process"] = None
            self.bot_cards[name].update_status("offline", "Parado")
            self.log(f"Bot '{name}' parado com sucesso.")
        else:
            self.bot_cards[name].update_status("offline", "Parado")
            self.log(f"Bot '{name}' já estava parado.")
        self.update_status_summary()

    def start_all_bots(self):
        self.log("Iniciando todos os bots iterativamente...")
        bot_names = list(bots.keys())
        for i, name in enumerate(bot_names):
            QTimer.singleShot(i * 1000, lambda n=name: self.start_bot(n))

    def stop_all_bots(self):
        self.log("Parando todos os bots...")
        for name in list(bots.keys()):
            self.stop_bot(name)

    def update_status_summary(self):
        online_count = sum(1 for bot in bots.values() if bot.get("process"))
        total_count = len(bots)
        self.status_summary.setText(f"{online_count} de {total_count} bots online")

    def open_schedule_dialog(self):
        dialog = ScheduleDialog(self, self.scheduled_times)
        if dialog.exec_() == QDialog.Accepted:
            self.scheduled_times = dialog.get_schedules()
            self.log(f"Agendamentos atualizados: {len(self.scheduled_times)} tarefa(s) salva(s).")
            self.save_schedules_to_disk()

    def check_scheduled_tasks(self):
        current_time = QTime.currentTime().toString("HH:mm")
        for schedule in self.scheduled_times:
            if schedule.get("start_time") == current_time:
                self.log(f"AGENDAMENTO: Iniciando todos os bots para a tarefa '{schedule['name']}'.")
                self.start_all_bots()
            if schedule.get("stop_time") == current_time:
                self.log(f"AGENDAMENTO: Parando todos os bots para a tarefa '{schedule['name']}'.")
                self.stop_all_bots()

    def load_schedules_from_disk(self):
        if not os.path.exists(self.SCHEDULE_FILE):
            return []
        try:
            with open(self.SCHEDULE_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_schedules_to_disk(self):
        try:
            with open(self.SCHEDULE_FILE, "w", encoding='utf-8') as f:
                json.dump(self.scheduled_times, f, indent=4)
            self.log(f"Agendamentos salvos com sucesso em '{self.SCHEDULE_FILE}'.")
        except Exception as e:
            self.log(f"ERRO CRÍTICO: Não foi possível salvar os agendamentos. {e}")


# =============================================================================
# JANELA DE DIÁLOGO PARA AGENDAMENTOS
# =============================================================================
class ScheduleDialog(QDialog):
    def __init__(self, parent, existing_schedules):
        super().__init__(parent)
        self.setWindowTitle("Gerenciar Agendamentos")
        self.setStyleSheet("background-color: #0D0D0D; color: #FFFFFF; font-family: 'Inter';")
        self.setMinimumSize(500, 500)
        self.current_schedules = list(existing_schedules)
        self.setup_ui()
        self.load_schedules_to_list_widget()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Adicionar/Editar Agendamento")
        title.setFont(QFont("Inter", 16, QFont.Bold))
        layout.addWidget(title)

        input_frame = QFrame()
        input_layout = QGridLayout(input_frame)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ex: Horário de trabalho")
        self.time_input_start = QTimeEdit()
        self.time_input_start.setDisplayFormat("HH:mm")
        self.time_input_stop = QTimeEdit()
        self.time_input_stop.setDisplayFormat("HH:mm")

        input_layout.addWidget(QLabel("Nome:"), 0, 0)
        input_layout.addWidget(self.name_input, 0, 1)
        input_layout.addWidget(QLabel("Horário de Início:"), 1, 0)
        input_layout.addWidget(self.time_input_start, 1, 1)
        input_layout.addWidget(QLabel("Horário de Parada:"), 2, 0)
        input_layout.addWidget(self.time_input_stop, 2, 1)
        
        self.add_button = ModernButton("Adicionar/Salvar", "primary")
        self.add_button.clicked.connect(self.add_or_update_schedule)
        input_layout.addWidget(self.add_button, 3, 0, 1, 2)
        layout.addWidget(input_frame)

        layout.addWidget(QLabel("Agendamentos Salvos:"))
        self.schedule_list = QListWidget()
        self.schedule_list.itemClicked.connect(self.populate_fields_for_editing)
        layout.addWidget(self.schedule_list)
        
        action_buttons_layout = QHBoxLayout()
        self.delete_button = ModernButton("Excluir Selecionado", "danger")
        self.delete_button.clicked.connect(self.delete_selected_schedule)
        self.clear_button = ModernButton("Limpar Campos", "secondary")
        self.clear_button.clicked.connect(self.clear_fields)
        action_buttons_layout.addWidget(self.clear_button)
        action_buttons_layout.addWidget(self.delete_button)
        layout.addLayout(action_buttons_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Save).setText("Salvar e Fechar")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def load_schedules_to_list_widget(self):
        self.schedule_list.clear()
        for schedule in self.current_schedules:
            item_text = f"{schedule['name']} (Início: {schedule['start_time']}, Fim: {schedule['stop_time']})"
            self.schedule_list.addItem(item_text)

    def clear_fields(self):
        self.name_input.clear()
        self.time_input_start.setTime(QTime(0, 0))
        self.time_input_stop.setTime(QTime(0, 0))
        self.schedule_list.clearSelection()

    def add_or_update_schedule(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Entrada Inválida", "O nome do agendamento não pode ser vazio.")
            return
        start_time = self.time_input_start.time().toString("HH:mm")
        stop_time = self.time_input_stop.time().toString("HH:mm")
        new_schedule = {"name": name, "start_time": start_time, "stop_time": stop_time}
        selected_row = self.schedule_list.currentRow()
        if selected_row != -1:
            self.current_schedules[selected_row] = new_schedule
        else:
            self.current_schedules.append(new_schedule)
        self.load_schedules_to_list_widget()
        self.clear_fields()

    def populate_fields_for_editing(self, item):
        row = self.schedule_list.row(item)
        schedule = self.current_schedules[row]
        self.name_input.setText(schedule["name"])
        self.time_input_start.setTime(QTime.fromString(schedule["start_time"], "HH:mm"))
        self.time_input_stop.setTime(QTime.fromString(schedule["stop_time"], "HH:mm"))

    def delete_selected_schedule(self):
        selected_row = self.schedule_list.currentRow()
        if selected_row == -1:
            QMessageBox.information(self, "Nenhuma Seleção", "Por favor, selecione um agendamento para excluir.")
            return

        reply = QMessageBox.question(self, "Confirmar Exclusão", "Tem certeza?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.current_schedules[selected_row]
            self.load_schedules_to_list_widget()
            self.clear_fields()

    def get_schedules(self):
        return self.current_schedules


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Criar settings.json empty se não existir, mas aqui assumimos que vai existir.
    
    window = BotManager()
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()