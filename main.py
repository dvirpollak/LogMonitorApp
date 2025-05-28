import sys
import os
import json
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QMessageBox, QListWidget, QListWidgetItem, QHBoxLayout,
    QInputDialog, QMenu, QFileDialog
)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QCursor

CONFIG_FILE = "monitor_config.json"

def show_manual():
    msg = QMessageBox()
    msg.setWindowTitle("User Manual")
    msg.setText("""
    Welcome to the Log Monitor App!

    - Add Log File: Add a new tab for a log.
    - Add/Edit/Remove Filters: Manage filters for matching lines.
    - Start Real-time Monitor: Open terminal and show log updates live.
    - Stop Monitoring: Stop the real-time process.
    - Cat in Terminal: View entire log in a terminal.
    - Cat to File: Save full log to a file.
    - Export to CSV: Save log in CSV format, parsing structured lines.
    

    Please read this manual before using the application.
    """)
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    result = msg.exec_()


def show_manual_if_required():
    if len(sys.argv) > 1:
        return
    show_manual()


class LogTab(QWidget):
    def __init__(self, parent, log_path="", filters=None):
        super().__init__()
        self.parent = parent
        self.log_path = log_path
        self.filters = filters if isinstance(filters, list) else []
        self.monitor_process = None
        self.monitor_timer = QTimer()
        self.monitor_timer.timeout.connect(self.check_monitor_status)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout.addWidget(QLabel("Log file path:"))
        self.path_input = QLineEdit(str(self.log_path))
        self.layout.addWidget(self.path_input)

        self.layout.addWidget(QLabel("Filters: (Check filters to use)"))
        self.filter_list = QListWidget()
        self.filter_list.setSelectionMode(QListWidget.SingleSelection)
        for f in self.filters:
            if isinstance(f, dict):
                self.add_filter_item(f["text"], f.get("enabled", True))
            else:
                self.add_filter_item(f, True)
        self.layout.addWidget(self.filter_list)

        self.new_filter_input = QLineEdit()
        self.new_filter_input.setPlaceholderText("Add new filter")
        self.layout.addWidget(self.new_filter_input)

        filter_buttons = QHBoxLayout()
        add_filter_btn = QPushButton("Add Filter")
        add_filter_btn.clicked.connect(self.add_filter)
        remove_filter_btn = QPushButton("Remove Selected")
        remove_filter_btn.clicked.connect(self.remove_filter)
        edit_filter_btn = QPushButton("Edit Selected")
        edit_filter_btn.clicked.connect(self.edit_filter)

        filter_buttons.addWidget(add_filter_btn)
        filter_buttons.addWidget(edit_filter_btn)
        filter_buttons.addWidget(remove_filter_btn)
        self.layout.addLayout(filter_buttons)

        monitor_buttons = QHBoxLayout()
        realtime_btn = QPushButton("Start Real-time Monitor")
        realtime_btn.clicked.connect(self.start_monitoring)
        self.stop_btn = QPushButton("Stop Monitoring")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_monitoring)

        monitor_buttons.addWidget(realtime_btn)
        monitor_buttons.addWidget(self.stop_btn)
        self.layout.addLayout(monitor_buttons)

        offline_buttons = QHBoxLayout()
        cat_terminal = QPushButton("Cat in Terminal")
        cat_terminal.clicked.connect(self.cat_terminal)
        cat_file = QPushButton("Cat to File")
        cat_file.clicked.connect(self.cat_to_file)
        export_csv = QPushButton("Export to CSV")
        export_csv.clicked.connect(self.export_to_csv)

        offline_buttons.addWidget(cat_terminal)
        offline_buttons.addWidget(cat_file)
        offline_buttons.addWidget(export_csv)
        self.layout.addLayout(offline_buttons)

        self.status_label = QLabel("")
        self.layout.addWidget(self.status_label)

    def add_filter_item(self, text, checked=True):
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.filter_list.addItem(item)

    def add_filter(self):
        text = self.new_filter_input.text().strip()
        if text and not self.filter_exists(text):
            self.add_filter_item(text)
            self.new_filter_input.clear()
            self.parent.save_config()

    def edit_filter(self):
        selected = self.filter_list.currentItem()
        if selected:
            new_text, ok = QInputDialog.getText(self, "Edit Filter", "Update filter:", text=selected.text())
            if ok and new_text.strip():
                selected.setText(new_text.strip())
                self.parent.save_config()

    def remove_filter(self):
        selected = self.filter_list.currentItem()
        if selected:
            self.filter_list.takeItem(self.filter_list.row(selected))
            self.parent.save_config()

    def filter_exists(self, text):
        return any(text == self.filter_list.item(i).text() for i in range(self.filter_list.count()))

    def get_all_filters(self):
        return [
            {
                "text": self.filter_list.item(i).text(),
                "enabled": self.filter_list.item(i).checkState() == Qt.Checked
            }
            for i in range(self.filter_list.count())
        ]

    def get_selected_filters(self):
        return [
            self.filter_list.item(i).text()
            for i in range(self.filter_list.count())
            if self.filter_list.item(i).checkState() == Qt.Checked
        ]

    def get_log_path(self):
        return self.path_input.text().strip()

    def start_monitoring(self):
        log_path = self.get_log_path()
        selected_filters = self.get_selected_filters()
        if not log_path:
            QMessageBox.warning(self, "Missing input", "Please provide a log file.")
            return
        command = f"tail -F '{log_path}'"
        for f in selected_filters:
            command += f" | grep --line-buffered '{f}'"
        try:
            self.monitor_process = subprocess.Popen([
                "gnome-terminal", "--", "bash", "-c", f"{command}; exec bash"
            ])
            self.status_label.setText("Monitoring started.")
            self.stop_btn.setEnabled(True)
            self.monitor_timer.start(1000)
        except FileNotFoundError:
            QMessageBox.critical(self, "Terminal error", "gnome-terminal not found.")

    def stop_monitoring(self):
        if self.monitor_process and self.monitor_process.poll() is None:
            self.monitor_process.terminate()
        self.monitor_process = None
        self.monitor_timer.stop()
        self.status_label.setText("Monitoring stopped.")
        self.stop_btn.setEnabled(False)

    def check_monitor_status(self):
        if self.monitor_process and self.monitor_process.poll() is not None:
            self.status_label.setText("Monitoring stopped (terminal closed).")
            self.stop_btn.setEnabled(False)
            self.monitor_timer.stop()
            self.monitor_process = None

    def cat_terminal(self):
        log_path = self.get_log_path()
        if log_path:
            subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f"cat '{log_path}'; exec bash"])

    def cat_to_file(self):
        log_path = self.get_log_path()
        if log_path:
            target, _ = QFileDialog.getSaveFileName(self, "Save Output", "output.txt")
            if target:
                with open(log_path) as f_in, open(target, 'w') as f_out:
                    f_out.write(f_in.read())

    def export_to_csv(self):
        log_path = self.get_log_path()
        if not log_path or not os.path.exists(log_path):
            QMessageBox.warning(self, "File Error", "Log file does not exist.")
            return
        target, _ = QFileDialog.getSaveFileName(self, "Save CSV", "output.csv")
        if not target:
            return
        with open(log_path, 'r') as f_in, open(target, 'w') as f_out:
            for line in f_in:
                parts = []
                if line.startswith("["):
                    parts = line.split("]")
                    parts = [p.strip("[\"] ") for p in parts if p.strip()]
                if len(parts) >= 4:
                    f_out.write(",".join(parts[:3]) + f',"{parts[3]}"\n')

class LogMonitorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Monitor")
        self.resize(800, 600)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        top_buttons = QHBoxLayout()
        self.add_tab_button = QPushButton("➕ Add New Log File")
        self.add_tab_button.clicked.connect(self.add_log_tab)
        help_button = QPushButton("❓ Help")
        help_button.clicked.connect(show_manual)
        top_buttons.addWidget(self.add_tab_button)
        top_buttons.addWidget(help_button)
        self.layout.addLayout(top_buttons)

        self.tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self.show_tab_context_menu)

        self.config = self.load_config()
        for log_path, filters in self.config.items():
            self.add_log_tab(log_path, filters)

    def add_log_tab(self, log_path="", filters=None):
        if isinstance(filters, bool):
            filters = []
        tab = LogTab(self, log_path, filters)
        display_name = os.path.basename(log_path) if log_path else "New Log"
        self.tabs.addTab(tab, display_name)

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'w') as f:
                json.dump({}, f)
        with open(CONFIG_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def save_config(self):
        new_config = {}
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            path = tab.get_log_path()
            if path:
                new_config[path] = tab.get_all_filters()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(new_config, f, indent=2)

    def show_tab_context_menu(self, pos: QPoint):
        tab_index = self.tabs.tabBar().tabAt(pos)
        if tab_index < 0:
            return
        menu = QMenu()
        rename_action = menu.addAction("Rename Tab")
        close_action = menu.addAction("Close Tab (Keep Config)")
        delete_action = menu.addAction("Delete Log Config")
        action = menu.exec_(self.tabs.mapToGlobal(pos))
        if action == rename_action:
            current_title = self.tabs.tabText(tab_index)
            new_title, ok = QInputDialog.getText(self, "Rename Tab", "New tab name:", text=current_title)
            if ok and new_title.strip():
                self.tabs.setTabText(tab_index, new_title.strip())
        elif action == close_action:
            self.tabs.removeTab(tab_index)
        elif action == delete_action:
            tab = self.tabs.widget(tab_index)
            log_path = tab.get_log_path()
            if log_path in self.config:
                del self.config[log_path]
                self.save_config()
            self.tabs.removeTab(tab_index)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    show_manual_if_required()
    app.setStyleSheet("""
        QWidget { background-color: #f8f9fa; color: #212529; font-size: 14px; }
        QLineEdit, QListWidget, QTextEdit {
            background-color: white; color: #212529; border: 1px solid #ced4da;
        }
        QPushButton {
            background-color: #007bff; color: white; padding: 6px; border-radius: 4px;
        }
        QPushButton:hover { background-color: #0056b3; }
        QLabel { font-weight: bold; }
    """)
    window = LogMonitorApp()
    window.show()
    sys.exit(app.exec_())
