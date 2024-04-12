import sys
import argparse
import subprocess

from minecraft_launcher_lib.utils import get_minecraft_directory, get_version_list
from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.command import get_minecraft_command
from random_username.generate import generate_username
from uuid import uuid1

class LaunchThread:
    def __init__(self, version_id, username):
        self.version_id = version_id
        self.username = username

    def launch_game(self):
        minecraft_directory = get_minecraft_directory().replace('minecraft', 'hexolauncher')

        install_minecraft_version(versionid=self.version_id, minecraft_directory=minecraft_directory)

        if self.username == '':
            self.username = generate_username()[0]

        options = {
            'username': self.username,
            'uuid': str(uuid1()),
            'token': ''
        }

        minecraft_command = get_minecraft_command(version=self.version_id, minecraft_directory=minecraft_directory, options=options)

        try:
            subprocess.Popen(minecraft_command, shell=True)  # Запускаем Minecraft через subprocess
        except Exception as e:
            print("Error launching Minecraft:", e)

def cli():
    parser = argparse.ArgumentParser(description='HexoLauncher CLI')
    parser.add_argument('version', type=str, help='Minecraft version')
    parser.add_argument('--username', type=str, default='', help='Minecraft username')

    args = parser.parse_args()

    launcher = LaunchThread(args.version, args.username)
    launcher.launch_game()

class MainWindow:
    def __init__(self):
        print("Welcome to HexoLauncher!")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cli()
    else:
        app = MainWindow()
