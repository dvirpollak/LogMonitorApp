import sys
import os
import json
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QTabWidget, QMessageBox, QListWidget, QListWidgetItem, QHBoxLayout,
    QInputDialog, QMenu
)
from PyQt5.QtCore import Qt, QPoint

CONFIG_FILE = "monitor_config.json"


class LogTab(QWidget):
    def __init__(self, parent, log_path="", filters=None):
        super().__init__()
        self.parent = parent
        self.log_path = log_path
        self.filters = filters if isinstance(filters, list) else []

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

        monitor_btn = QPushButton("Start Monitoring")
        monitor_btn.clicked.connect(self.start_monitoring)
        self.layout.addWidget(monitor_btn)

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
            subprocess.Popen([
                "gnome-terminal", "--", "bash", "-c", f"{command}; exec bash"
            ])
        except FileNotFoundError:
            QMessageBox.critical(self, "Terminal error", "gnome-terminal not found. Install or update the terminal command.")


class LogMonitorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Monitor")
        self.resize(700, 500)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.add_tab_button = QPushButton("➕ Add New Log File")
        self.add_tab_button.clicked.connect(self.add_log_tab)
        self.layout.addWidget(self.add_tab_button)

        # Add tab context menu
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
    window = LogMonitorApp()
    window.show()
    sys.exit(app.exec_())
