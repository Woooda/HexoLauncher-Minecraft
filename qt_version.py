import json
import logging
import os
import re
import requests
import shutil
import subprocess

import coloredlogs
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QApplication, QCheckBox, QLineEdit, QMainWindow,
 QPushButton, QRadioButton, QVBoxLayout, QWidget,
 QLabel, QListWidget, QProgressBar, QMessageBox, QComboBox)

try:
 from minecraft_launcher_lib.command import get_minecraft_command
 from minecraft_launcher_lib.install import install_minecraft_version
 from minecraft_launcher_lib.utils import get_minecraft_directory, get_version_list
except ImportError as e:
    logging.error(f"Missing required module: {e}. Please ensure minecraft_launcher_lib is installed.")
    exit(1)

from random_username.generate import generate_username
from uuid import uuid1

# Configure logging with levels and colors
log_format = '%(asctime)s - %(levelname)s - %(message)s'
coloredlogs.DEFAULT_LOG_FORMAT = '%(asctime)s - %(asctime)s - %(levelname)s - %(message)s'
coloredlogs.DEFAULT_LEVEL_STYLES = {
    'debug': {'color': 'green'},
    'info': {'color': 'blue'},
    'warning': {'color': 'yellow'},
    'error': {'color': 'red', 'bold': True},
    'critical': {'color': 'red', 'bold': True, 'background': 'white'}
}
coloredlogs.DEFAULT_FIELD_STYLES = {
    'asctime': {'color': 'magenta'},
    'levelname': {'color': 'cyan', 'bold': True}
}
coloredlogs.install(level='DEBUG', fmt=log_format)

# Configure file logging
file_handler = logging.FileHandler('launcher.log')
file_handler.setFormatter(logging.Formatter(log_format))
file_handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(file_handler)

minecraft_directory = get_minecraft_directory().replace('minecraft', 'hexolauncher')
config_file = os.path.join(minecraft_directory, 'launcher_config.json')
logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'minecraft_logo.png')

# Создать директорию для конфигурации, если она не существует
os.makedirs(minecraft_directory, exist_ok=True)

def load_config():
    if os.path.exists(config_file):
        with open(config_file, 'r') as file:
            return json.load(file)
    return {}

def save_config(config):
    # Создать директорию, если она не существует
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    # Сохранить конфигурацию в файл
    with open(config_file, 'w') as file:
        json.dump(config, file, indent=4)

class LaunchThread(QThread):
    launch_setup_signal = pyqtSignal(str, str, str, bool)
    progress_update_signal = pyqtSignal(int, int, str)
    state_update_signal = pyqtSignal(bool)
    forge_error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.version_id = ''
        self.username = ''
        self.minecraft_folder = ''
        self.install_forge = False
        self.progress = 0
        self.progress_max = 0
        self.progress_label = ''
        self.launch_setup_signal.connect(self.launch_setup)

    def launch_setup(self, version_id, username, minecraft_folder, install_forge):
        self.version_id = version_id
        self.username = username
        self.minecraft_folder = minecraft_folder
        self.install_forge = install_forge

    def update_progress_label(self, value):
        self.progress_label = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)
    
    def update_progress(self, value):
        self.progress = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)
    
    def update_progress_max(self, value):
        self.progress_max = value
        self.progress_update_signal.emit(self.progress, self.progress_max, self.progress_label)

    def download_forge(self):
        self.update_progress_label('Downloading Forge...')
        forge_installer_url = f'https://files.minecraftforge.net/maven/net/minecraftforge/forge/{self.version_id}-recommended/forge-{self.version_id}-recommended-installer.jar'
        try:
            response = requests.get(forge_installer_url, stream=True)
            response.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"Error downloading Forge: {e}")
            return None
        
        installer_path = os.path.join(self.minecraft_folder, 'forge_installer.jar')
        try:
            with open(installer_path, 'wb') as installer_file:
                total_length = response.headers.get('content-length')
                if total_length is None:  # no content length header
                    installer_file.write(response.content)
                else:
                    dl = 0
                    total_length = int(total_length)
                    for data in response.iter_content(chunk_size=4096):
                        dl += len(data)
                        installer_file.write(data)
                        self.update_progress(dl * 100 // total_length)
        except IOError as e:
            logging.error(f"Error saving Forge installer: {e}")
            return None
        
        return installer_path

    def install_forge(self, installer_path):
        if installer_path is None:
            logging.error("Installer path is None, skipping Forge installation.")
            return
        self.update_progress_label('Installing Forge...')
        try:
            subprocess.run(['java', '-jar', installer_path, '--installClient', '--minecraftDir', self.minecraft_folder], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error installing Forge: {e}")

    def run(self):
        self.state_update_signal.emit(True)
        logging.info(f'Starting installation: version={self.version_id}, forge={self.install_forge}')

        # Install Minecraft version
        try:
            logging.debug("Installing Minecraft version")
            install_minecraft_version(versionid=self.version_id, minecraft_directory=self.minecraft_folder, callback={ 'setStatus': self.update_progress_label, 'setProgress': self.update_progress, 'setMax': self.update_progress_max })
            logging.debug("Minecraft version installed successfully")
        except Exception as e:
            logging.error(f"Error installing Minecraft version: {e}")
            self.state_update_signal.emit(False)
            return

        # Install Forge if selected
        if self.install_forge:
            logging.info('Forge installation selected')
            installer_path = self.download_forge()
            if installer_path:
                self.install_forge(installer_path)
            else:
                self.forge_error_signal.emit(f'Forge version for Minecraft {self.version_id} does not exist.')

        if self.username == '':
            self.username = generate_username()[0]
        
        options = {
            'username': self.username,
            'uuid': str(uuid1()),
            'token': ''
        }

        minecraft_command = get_minecraft_command(version=self.version_id, minecraft_directory=self.minecraft_folder, options=options)
        logging.debug(f"Generated Minecraft command: {' '.join(minecraft_command)}")

        try:
            # Save the command to a batch file to avoid long command line issues
            command_file = os.path.join(self.minecraft_folder, 'launch_minecraft.bat')
            with open(command_file, 'w') as file:
                file.write(' '.join(minecraft_command))
            logging.info('Launching Minecraft')
            subprocess.Popen(command_file, shell=True)
            logging.info('Minecraft launched successfully')
        except Exception as e:
            logging.error(f'Error launching Minecraft: {e}')

        self.state_update_signal.emit(False)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("HexoLauncher")
        self.setStyleSheet("color: white; background-color: #000F1A;")

        self.centralwidget = QWidget(self)

        self.logo = QLabel(self.centralwidget)
        self.logo.setAlignment(Qt.AlignCenter)
        self.set_logo_icon(logo_path)

        self.description = QLabel(self.centralwidget)
        self.description.setText("Welcome! Choose your Minecraft version:")
        self.description.setAlignment(Qt.AlignCenter)
        self.description.setStyleSheet("font-size: 16px;")

        self.version_list = QListWidget(self.centralwidget)
        self.version_list.setStyleSheet("font-size: 14px; background-color: #34495E; border: 1px solid #2C3E50; border-radius: 5px; padding: 5px; color: white;")
        self.populate_version_list()

        self.username = QLineEdit(self.centralwidget)
        self.username.setPlaceholderText('Enter Username')
        self.username.setAlignment(Qt.AlignCenter)
        self.username.setStyleSheet("font-size: 14px; background-color: #34495E; border: 1px solid #2C3E50; border-radius: 5px; padding: 5px; color: white;")

        self.minecraft_folder = QLineEdit(self.centralwidget)
        self.minecraft_folder.setPlaceholderText('Enter Minecraft Folder')
        self.minecraft_folder.setAlignment(Qt.AlignCenter)
        self.minecraft_folder.setStyleSheet("font-size: 14px; background-color: #34495E; border: 1px solid #2C3E50; border-radius: 5px; padding: 5px; color: white;")

        self.install_forge_checkbox = QCheckBox('Install Forge', self.centralwidget)
        self.install_forge_checkbox.setStyleSheet("color: white;")

        self.start_progress = QProgressBar(self.centralwidget)
        self.start_progress.setVisible(False)
        self.start_progress.setStyleSheet("QProgressBar { color: #3498DB; border: 1px solid #2C3E50; border-radius: 5px; background-color: #34495E; } QProgressBar::chunk { background-color: #2E86C1; }")

        self.start_button = QPushButton(self.centralwidget)
        self.start_button.setText('Play')
        self.start_button.setStyleSheet("QPushButton { background-color: #3498DB; color: white; border: none; border-radius: 5px; padding: 10px; font-size: 16px; } QPushButton:hover { background-color: #2E86C1; }")
        self.start_button.clicked.connect(self.launch_game)

        self.white_style_button = QRadioButton("White Style", self.centralwidget)
        self.white_style_button.setChecked(False)
        self.white_style_button.setStyleSheet("color: white;")
        self.white_style_button.toggled.connect(lambda:self.set_style("white"))

        self.black_style_button = QRadioButton("Black Style", self.centralwidget)
        self.black_style_button.setChecked(True)
        self.black_style_button.setStyleSheet("color: white;")
        self.black_style_button.toggled.connect(lambda:self.set_style("black"))

        self.theme_selector = QComboBox(self.centralwidget)
        self.theme_selector.addItem("Dark")
        self.theme_selector.addItem("Light")
        self.theme_selector.currentTextChanged.connect(self.change_theme)

        self.vertical_layout = QVBoxLayout(self.centralwidget)
        self.vertical_layout.addWidget(self.logo)
        self.vertical_layout.addWidget(self.description)
        self.vertical_layout.addWidget(self.version_list)
        self.vertical_layout.addWidget(self.username)
        self.vertical_layout.addWidget(self.minecraft_folder)
        self.vertical_layout.addWidget(self.install_forge_checkbox)
        self.vertical_layout.addWidget(self.theme_selector)
        self.vertical_layout.addWidget(self.start_progress)
        self.vertical_layout.addWidget(self.start_button)
        self.vertical_layout.setAlignment(Qt.AlignCenter)

        self.launch_thread = LaunchThread()
        self.launch_thread.state_update_signal.connect(self.state_update)
        self.launch_thread.progress_update_signal.connect(self.update_progress)
        self.launch_thread.forge_error_signal.connect(self.show_forge_error)

        self.setCentralWidget(self.centralwidget)
        
        # Load configuration
        self.config = load_config()
        self.apply_config()

        # Set initial style to black
        self.set_style("black")

    def apply_config(self):
        self.username.setText(self.config.get('username', ''))
        self.minecraft_folder.setText(self.config.get('minecraft_folder', minecraft_directory))
        if self.config.get('style') == 'white':
            self.white_style_button.setChecked(True)
        else:
            self.black_style_button.setChecked(True)

    def save_config(self):
        self.config['username'] = self.username.text()
        self.config['minecraft_folder'] = self.minecraft_folder.text()
        self.config['style'] = 'white' if self.white_style_button.isChecked() else 'black'
        save_config(self.config)

    def set_logo_icon(self, path):
        if os.path.exists(path):
            pixmap = QPixmap(path)
            self.logo.setPixmap(pixmap.scaledToHeight(200)) 
        else:
            logging.warning(f"Logo file not found: {path}")
            QMessageBox.warning(self, "Error", f"Logo file not found: {path}")

    def populate_version_list(self):
        try:
            versions = get_version_list()
            filtered_versions = self.filter_versions(versions)
            sorted_versions = sorted(filtered_versions, key=lambda v: list(map(int, re.findall(r'\d+', v))), reverse=True)
            for version in sorted_versions:
                self.version_list.addItem(version)
        except Exception as e:
            logging.error(f"Error fetching version list: {e}")
            QMessageBox.warning(self, "Error", "Failed to fetch version list")

    def filter_versions(self, versions):
        filtered = set()
        pattern = re.compile(r'^\d+\.\d+\.\d+$')
        forge_pattern = re.compile(r'^\d+\.\d+\.\d+-forge$')
        for version in versions:
            if pattern.match(version['id']):
                filtered.add(version['id'])
            if forge_pattern.match(version['id']):
                base_version = version['id'].split('-')[0]
                forge_version = f"{base_version} Forge"
                if self.check_forge_exists(base_version):
                    filtered.add(forge_version)
        return filtered

    def check_forge_exists(self, base_version):
        forge_installer_url = f'https://files.minecraftforge.net/maven/net/minecraftforge/forge/{base_version}-recommended/forge-{base_version}-recommended-installer.jar'
        try:
            response = requests.head(forge_installer_url)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def show_forge_error(self, message):
        QMessageBox.warning(self, "Forge Installation Error", message)

    def validate_input(self):
        if not self.username.text().strip():
            QMessageBox.warning(self, "Input Error", "Username cannot be empty")
            return False
        if not self.minecraft_folder.text().strip():
            QMessageBox.warning(self, "Input Error", "Minecraft folder cannot be empty")
            return False
        return True

    def state_update(self, value):
        self.start_button.setDisabled(value)
        self.start_progress.setVisible(value)

    def update_progress(self, progress, max_progress, label):
        self.start_progress.setValue(progress)
        self.start_progress.setMaximum(max_progress)
        self.start_progress.setFormat(label)

    def launch_game(self):
        if not self.validate_input():
            return
        selected_version = self.version_list.currentItem().text()
        install_forge = self.install_forge_checkbox.isChecked()
        if 'Forge' in selected_version:
            selected_version = selected_version.replace(' Forge', '')
            install_forge = True
        self.launch_thread.launch_setup_signal.emit(selected_version, self.username.text(), self.minecraft_folder.text(), install_forge)
        self.launch_thread.start()
        self.save_config()

    def set_style(self, style):
        if style == "white":
            self.setStyleSheet("color: black; background-color: white;")
        elif style == "black":
            self.setStyleSheet("color: white; background-color: #000F1A;")

    def change_theme(self, theme):
        if theme == "Dark":
            self.set_style("black")
        elif theme == "Light":
            self.set_style("white")

    def show_error_message(self, title, message):
        QMessageBox.critical(self, title, message)

    def check_for_updates(self):
        current_version = "1.0.0"
        update_url = "https://example.com/launcher/update"
        try:
            response = requests.get(update_url)
            latest_version = response.json().get('version')
            if latest_version > current_version:
                self.download_and_install_update(response.json().get('download_url'))
        except Exception as e:
            logging.error(f"Error checking for updates: {e}")

    def download_and_install_update(self, download_url):
        # Download and install update logic
        pass

    def backup_data(self):
        backup_folder = os.path.join(self.minecraft_folder, "backup")
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)
        # Copy necessary files to backup folder
        shutil.copytree(self.minecraft_folder, backup_folder)

    def restore_data(self):
        backup_folder = os.path.join(self.minecraft_folder, "backup")
        if os.path.exists(backup_folder):
            # Restore files from backup folder
            shutil.copytree(backup_folder, self.minecraft_folder)

if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
