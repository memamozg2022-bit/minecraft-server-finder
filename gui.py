"""
GUI для Minecraft Server Scanner на PyQt6
"""
import sys
import asyncio
import socket
from typing import List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QSpinBox,
    QLabel, QComboBox, QProgressBar, QTabWidget, QGroupBox, QMessageBox,
    QHeaderView, QDialog, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtCore import QSize

from minecraft_scanner import MinecraftServerScanner, get_local_network_ip, generate_ip_range


class ScannerWorker(QThread):
    """Рабочий поток для сканирования серверов"""

    progress = pyqtSignal(str, bool)  # (ip, found)
    finished = pyqtSignal(list)  # список найденных серверов
    error = pyqtSignal(str)

    def __init__(self, ip_list: List[str], port: int = 25565, max_concurrent: int = 50):
        super().__init__()
        self.ip_list = ip_list
        self.port = port
        self.max_concurrent = max_concurrent
        self.scanner = MinecraftServerScanner()

    def run(self):
        """Запускает сканирование в отдельном потоке"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def callback(ip, found):
                self.progress.emit(ip, found)

            servers = loop.run_until_complete(
                self.scanner.scan_ips_concurrent(
                    self.ip_list,
                    port=self.port,
                    max_concurrent=self.max_concurrent,
                    callback=callback
                )
            )

            self.finished.emit(servers)
            loop.close()

        except Exception as e:
            self.error.emit(str(e))


class MinecraftServerFinderGUI(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎮 Minecraft Server Finder")
        self.setGeometry(100, 100, 1200, 700)
        self.setStyleSheet(self._get_stylesheet())

        self.scanner_worker: Optional[ScannerWorker] = None
        self.found_servers = []
        self.scanning = False

        self._init_ui()
        self._setup_styles()

    def _get_stylesheet(self) -> str:
        """Возвращает CSS стили приложения"""
        return """
        QMainWindow {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QWidget {
            background-color: #1e1e1e;
            color: #ffffff;
        }
        QTableWidget {
            background-color: #2d2d2d;
            color: #ffffff;
            gridline-color: #404040;
            border: 1px solid #404040;
        }
        QTableWidget::item {
            padding: 5px;
            border-bottom: 1px solid #404040;
        }
        QTableWidget::item:selected {
            background-color: #0d47a1;
        }
        QHeaderView::section {
            background-color: #0d47a1;
            color: #ffffff;
            padding: 5px;
            border: none;
            font-weight: bold;
        }
        QPushButton {
            background-color: #0d47a1;
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: bold;
            font-size: 11px;
        }
        QPushButton:hover {
            background-color: #1565c0;
        }
        QPushButton:pressed {
            background-color: #0d47a1;
        }
        QPushButton:disabled {
            background-color: #505050;
            color: #a0a0a0;
        }
        QLineEdit, QSpinBox, QComboBox {
            background-color: #2d2d2d;
            color: #ffffff;
            border: 1px solid #404040;
            border-radius: 3px;
            padding: 5px;
            selection-background-color: #0d47a1;
        }
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
            border: 1px solid #0d47a1;
        }
        QLabel {
            color: #ffffff;
        }
        QGroupBox {
            color: #ffffff;
            border: 1px solid #404040;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }
        QProgressBar {
            background-color: #2d2d2d;
            border: 1px solid #404040;
            border-radius: 3px;
            text-align: center;
            color: #ffffff;
        }
        QProgressBar::chunk {
            background-color: #0d47a1;
        }
        QTabWidget::pane {
            border: 1px solid #404040;
        }
        QTabBar::tab {
            background-color: #2d2d2d;
            color: #ffffff;
            padding: 8px 20px;
            border: 1px solid #404040;
        }
        QTabBar::tab:selected {
            background-color: #0d47a1;
            border: 1px solid #0d47a1;
        }
        """

    def _init_ui(self):
        """Инициализирует UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Создаем tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Вкладка "Сканирование"
        self._create_scan_tab()

        # Вкладка "Серверы"
        self._create_servers_tab()

        # Вкладка "Настройки"
        self._create_settings_tab()

    def _create_scan_tab(self):
        """Создает вкладку сканирования"""
        scan_widget = QWidget()
        layout = QVBoxLayout()
        scan_widget.setLayout(layout)

        # Группа настроек сканирования
        settings_group = QGroupBox("⚙️ Параметры сканирования")
        settings_layout = QVBoxLayout()

        # Базовый IP
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("Базовый IP адрес:"))
        self.base_ip_input = QLineEdit()
        local_ip = get_local_network_ip()
        base_ip = ".".join(local_ip.split(".")[:3])
        self.base_ip_input.setText(base_ip)
        self.base_ip_input.setToolTip(f"Локальный IP: {local_ip}")
        ip_layout.addWidget(self.base_ip_input)
        settings_layout.addLayout(ip_layout)

        # Диапазон IP
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("Диапазон IP:"))
        self.range_start_spin = QSpinBox()
        self.range_start_spin.setValue(1)
        self.range_start_spin.setMaximum(254)
        range_layout.addWidget(self.range_start_spin)
        range_layout.addWidget(QLabel("-"))
        self.range_end_spin = QSpinBox()
        self.range_end_spin.setValue(100)
        self.range_end_spin.setMaximum(254)
        range_layout.addWidget(self.range_end_spin)
        range_layout.addStretch()
        settings_layout.addLayout(range_layout)

        # Порт
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Порт сервера:"))
        self.port_spin = QSpinBox()
        self.port_spin.setValue(25565)
        self.port_spin.setMinimum(1)
        self.port_spin.setMaximum(65535)
        port_layout.addWidget(self.port_spin)
        port_layout.addStretch()
        settings_layout.addLayout(port_layout)

        # Одновременные соединения
        concurrent_layout = QHBoxLayout()
        concurrent_layout.addWidget(QLabel("Макс. одновременных соединений:"))
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setValue(50)
        self.concurrent_spin.setMinimum(1)
        self.concurrent_spin.setMaximum(200)
        concurrent_layout.addWidget(self.concurrent_spin)
        concurrent_layout.addStretch()
        settings_layout.addLayout(concurrent_layout)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Группа управления сканированием
        control_group = QGroupBox("🎯 Управление сканированием")
        control_layout = QVBoxLayout()

        # Кнопки управления
        button_layout = QHBoxLayout()
        self.scan_button = QPushButton("▶ Начать сканирование")
        self.scan_button.clicked.connect(self._start_scan)
        button_layout.addWidget(self.scan_button)

        self.stop_button = QPushButton("⏹ Остановить")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop_scan)
        button_layout.addWidget(self.stop_button)

        self.clear_button = QPushButton("🗑 Очистить результаты")
        self.clear_button.clicked.connect(self._clear_results)
        button_layout.addWidget(self.clear_button)

        control_layout.addLayout(button_layout)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        control_layout.addWidget(self.progress_bar)

        # Информация о ходе сканирования
        self.status_label = QLabel("Статус: готов к сканированию")
        self.status_label.setStyleSheet("color: #90caf9; font-weight: bold;")
        control_layout.addWidget(self.status_label)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # Таблица процесса сканирования
        scan_group = QGroupBox("📋 Процесс сканирования")
        scan_table_layout = QVBoxLayout()

        self.scan_progress_table = QTableWidget()
        self.scan_progress_table.setColumnCount(3)
        self.scan_progress_table.setHorizontalHeaderLabels(["IP адрес", "Статус", "Время"])
        self.scan_progress_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.scan_progress_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.scan_progress_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.scan_progress_table.setMaximumHeight(150)

        scan_table_layout.addWidget(self.scan_progress_table)
        scan_group.setLayout(scan_table_layout)
        layout.addWidget(scan_group)

        layout.addStretch()
        self.tabs.addTab(scan_widget, "🔎 Сканирование")

    def _create_servers_tab(self):
        """Создает вкладку списка найденных серверов"""
        servers_widget = QWidget()
        layout = QVBoxLayout()
        servers_widget.setLayout(layout)

        # Статистика
        stats_layout = QHBoxLayout()
        self.servers_count_label = QLabel("Найдено серверов: 0")
        self.servers_count_label.setStyleSheet("font-weight: bold; color: #4caf50;")
        stats_layout.addWidget(self.servers_count_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        # Таблица серверов
        self.servers_table = QTableWidget()
        self.servers_table.setColumnCount(7)
        self.servers_table.setHorizontalHeaderLabels([
            "IP:Порт",
            "Версия",
            "MOTD",
            "Игроки",
            "Макс.",
            "Протокол",
            "Статус"
        ])

        header = self.servers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.servers_table)

        # Кнопки действий
        button_layout = QHBoxLayout()
        
        copy_button = QPushButton("📋 Скопировать IP:Порт")
        copy_button.clicked.connect(self._copy_selected_server)
        button_layout.addWidget(copy_button)

        refresh_button = QPushButton("🔄 Обновить таблицу")
        refresh_button.clicked.connect(self._update_servers_table)
        button_layout.addWidget(refresh_button)

        export_button = QPushButton("💾 Экспортировать")
        export_button.clicked.connect(self._export_servers)
        button_layout.addWidget(export_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.tabs.addTab(servers_widget, "🎮 Серверы")

    def _create_settings_tab(self):
        """Создает вкладку настроек"""
        settings_widget = QWidget()
        layout = QVBoxLayout()
        settings_widget.setLayout(layout)

        # Информация о приложении
        info_group = QGroupBox("ℹ️ Информация")
        info_layout = QVBoxLayout()

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setPlainText("""
Minecraft Server Finder - утилита для поиска локальных серверов Minecraft в вашей сети.

📋 Возможности:
• Асинхронное сканирование 10-100+ IP адресов одновременно
• Проверка версии протокола Minecraft
• Отображение информации о серверах (MOTD, количество игроков и т.д.)
• Экспорт результатов
• Фильтрация по версиям

🚀 Как использовать:
1. Перейдите на вкладку "Сканирование"
2. Установите параметры (базовый IP, диапазон, порт)
3. Нажмите "Начать сканирование"
4. Результаты появятся на вкладке "Серверы"

⚙️ Параметры:
• Базовый IP: первые три октета вашего локального IP (например: 192.168.1)
• Диапазон: последний октет диапазона сканирования (1-254)
• Одновременные соединения: 50 - оптимальное значение

🔧 Требования:
• Python 3.8+
• aiohttp для асинхронных запросов
• PyQt6 для графического интерфейса

📝 Версия: 1.0.0
🎨 Дизайн: Dark Mode
        """)
        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Быстрые ссылки
        links_group = QGroupBox("🔗 Быстрые действия")
        links_layout = QVBoxLayout()

        about_button = QPushButton("About")
        about_button.clicked.connect(self._show_about)
        links_layout.addWidget(about_button)

        links_group.setLayout(links_layout)
        layout.addWidget(links_group)

        layout.addStretch()
        self.tabs.addTab(settings_widget, "⚙️ Настройки")

    def _setup_styles(self):
        """Устанавливает стили для приложения"""
        pass

    def _start_scan(self):
        """Начинает сканирование"""
        if self.scanning:
            return

        base_ip = self.base_ip_input.text().strip()
        if not self._validate_ip(base_ip):
            QMessageBox.warning(self, "Ошибка", "Некорректный базовый IP адрес")
            return

        start = self.range_start_spin.value()
        end = self.range_end_spin.value()

        if start > end:
            QMessageBox.warning(self, "Ошибка", "Начальный IP не может быть больше конечного")
            return

        port = self.port_spin.value()
        max_concurrent = self.concurrent_spin.value()

        # Генерируем список IP
        ip_list = generate_ip_range(base_ip, start, end)

        # Создаем рабочий поток
        self.scanner_worker = ScannerWorker(ip_list, port, max_concurrent)
        self.scanner_worker.progress.connect(self._on_scan_progress)
        self.scanner_worker.finished.connect(self._on_scan_finished)
        self.scanner_worker.error.connect(self._on_scan_error)

        self.scanning = True
        self.scan_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.base_ip_input.setEnabled(False)
        self.range_start_spin.setEnabled(False)
        self.range_end_spin.setEnabled(False)
        self.port_spin.setEnabled(False)
        self.concurrent_spin.setEnabled(False)

        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(ip_list))
        self.scan_progress_table.setRowCount(0)

        self.status_label.setText(f"🔄 Статус: сканирование {len(ip_list)} адресов...")
        self.scanner_worker.start()

    def _stop_scan(self):
        """Останавливает сканирование"""
        if self.scanner_worker:
            self.scanner_worker.terminate()
            self.scanner_worker.wait()
        self._reset_ui()

    def _on_scan_progress(self, ip: str, found: bool):
        """Обновляет прогресс сканирования"""
        row = self.scan_progress_table.rowCount()
        self.scan_progress_table.insertRow(row)

        ip_item = QTableWidgetItem(ip)
        status_item = QTableWidgetItem("✅ Найден" if found else "❌ Нет")

        if found:
            status_item.setForeground(QColor("#4caf50"))
        else:
            status_item.setForeground(QColor("#f44336"))

        time_item = QTableWidgetItem(datetime.now().strftime("%H:%M:%S"))

        self.scan_progress_table.setItem(row, 0, ip_item)
        self.scan_progress_table.setItem(row, 1, status_item)
        self.scan_progress_table.setItem(row, 2, time_item)

        # Прокручиваем таблицу вниз
        self.scan_progress_table.scrollToBottom()

        # Обновляем прогресс-бар
        current = self.progress_bar.value()
        self.progress_bar.setValue(current + 1)

    def _on_scan_finished(self, servers: List):
        """Вызывается при завершении сканирования"""
        self.found_servers = servers
        self._update_servers_table()
        self._reset_ui()

        self.status_label.setText(
            f"✅ Статус: сканирование завершено. Найдено {len(servers)} серверов"
        )
        self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")

        if servers:
            self.tabs.setCurrentIndex(1)  # Переходим на вкладку серверов

    def _on_scan_error(self, error: str):
        """Вызывается при ошибке сканирования"""
        QMessageBox.critical(self, "Ошибка сканирования", f"Ошибка: {error}")
        self._reset_ui()

    def _reset_ui(self):
        """Сбрасывает UI в исходное состояние"""
        self.scanning = False
        self.scan_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.base_ip_input.setEnabled(True)
        self.range_start_spin.setEnabled(True)
        self.range_end_spin.setEnabled(True)
        self.port_spin.setEnabled(True)
        self.concurrent_spin.setEnabled(True)

    def _update_servers_table(self):
        """Обновляет таблицу серверов"""
        self.servers_table.setRowCount(0)

        for server in self.found_servers:
            row = self.servers_table.rowCount()
            self.servers_table.insertRow(row)

            # IP:Port
            ip_item = QTableWidgetItem(f"{server.host}:{server.port}")
            ip_item.setForeground(QColor("#2196f3"))

            # Version
            version_item = QTableWidgetItem(server.version)

            # MOTD
            motd_item = QTableWidgetItem(server.motd[:50])

            # Players Online
            players_item = QTableWidgetItem(str(server.players_online))

            # Max Players
            max_item = QTableWidgetItem(str(server.players_max))

            # Protocol
            protocol_item = QTableWidgetItem(str(server.protocol_version))

            # Status
            status_item = QTableWidgetItem("🟢 Онлайн")
            status_item.setForeground(QColor("#4caf50"))

            self.servers_table.setItem(row, 0, ip_item)
            self.servers_table.setItem(row, 1, version_item)
            self.servers_table.setItem(row, 2, motd_item)
            self.servers_table.setItem(row, 3, players_item)
            self.servers_table.setItem(row, 4, max_item)
            self.servers_table.setItem(row, 5, protocol_item)
            self.servers_table.setItem(row, 6, status_item)

        self.servers_count_label.setText(f"Найдено серверов: {len(self.found_servers)}")

    def _clear_results(self):
        """Очищает результаты сканирования"""
        self.found_servers = []
        self.servers_table.setRowCount(0)
        self.scan_progress_table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.status_label.setText("Статус: готов к сканированию")
        self.status_label.setStyleSheet("color: #90caf9; font-weight: bold;")
        self.servers_count_label.setText("Найдено серверов: 0")

    def _copy_selected_server(self):
        """Копирует IP:порт выбранного сервера в буфер обмена"""
        selected_rows = self.servers_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.information(self, "Информация", "Выберите сервер")
            return

        row = selected_rows[0].row()
        ip_text = self.servers_table.item(row, 0).text()

        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(ip_text)

        QMessageBox.information(self, "Успех", f"IP адрес скопирован: {ip_text}")

    def _export_servers(self):
        """Экспортирует список серверов"""
        if not self.found_servers:
            QMessageBox.warning(self, "Ошибка", "Нет серверов для экспорта")
            return

        filename = f"minecraft_servers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("Список найденных Minecraft серверов\n")
                f.write(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Всего серверов: {len(self.found_servers)}\n")
                f.write("=" * 80 + "\n\n")

                for i, server in enumerate(self.found_servers, 1):
                    f.write(f"{i}. {server.host}:{server.port}\n")
                    f.write(f"   Версия: {server.version}\n")
                    f.write(f"   MOTD: {server.motd}\n")
                    f.write(f"   Игроки: {server.players_online}/{server.players_max}\n")
                    f.write(f"   Протокол: {server.protocol_version}\n")
                    f.write("\n")

            QMessageBox.information(self, "Успех", f"Результаты экспортированы в {filename}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при экспорте: {e}")

    def _show_about(self):
        """Показывает информацию о приложении"""
        QMessageBox.about(
            self,
            "О программе",
            "🎮 Minecraft Server Finder v1.0.0\n\n"
            "Утилита для поиска локальных серверов Minecraft в вашей сети.\n\n"
            "✨ Возможности:\n"
            "• Асинхронное сканирование\n"
            "• Проверка версии протокола\n"
            "• Отображение информации о серверах\n"
            "• Экспорт результатов\n\n"
            "🚀 Разработано с использованием:\n"
            "• Python 3.8+\n"
            "• aiohttp\n"
            "• PyQt6"
        )

    @staticmethod
    def _validate_ip(ip: str) -> bool:
        """Проверяет корректность IP адреса"""
        parts = ip.split(".")
        if len(parts) != 3:
            return False
        try:
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except ValueError:
            return False


def main():
    """Главная функция приложения"""
    app = QApplication(sys.argv)
    window = MinecraftServerFinderGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
