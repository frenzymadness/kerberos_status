import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction, QApplication, QMenu, QSystemTrayIcon

_DIR = Path(__file__).parent
_IMAGES = _DIR / "images"
_re_info = re.compile(
    r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\s+(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\s+\S+@(\S+)"
)
_icon_files = {
    "redhat.com": _IMAGES / "key-red.png",
    "fedoraproject.org": _IMAGES / "key-blue.png",
    "other": _IMAGES / "key-yellow.png",
    "inactive": _IMAGES / "key-grey.png",
}


def tickets_from_klist():
    tickets = {}
    try:
        result = subprocess.run(["klist", "-A"], capture_output=True, text=True)
        output = result.stdout.strip()
    except Exception as e:
        print(f"Error: {e}")

    for line in output.splitlines():
        try:
            ticket = Ticket(line)
        except Exception:
            pass
            # print(f"error converting line to ticket: {line}")
        else:
            tickets[ticket.principal] = ticket

    return tickets


class Icon:
    def __init__(self, object, menu=None, expires=None):
        self.object = object
        self.menu = menu
        self.expires = expires


class Ticket:
    def __init__(self, line):
        match = _re_info.match(line)
        if match:
            # start_str = match.group(1)
            expires_str = match.group(2)
            self.principal = match.group(3).lower()

            self.expires = datetime.strptime(expires_str, "%m/%d/%Y %H:%M:%S")
        else:
            raise ValueError(f"Wrong input for Ticket: {line}")

    def is_active(self):
        return self.expires > datetime.now()


class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.icons = {}

        self.tickets = tickets_from_klist()

        for principal, ticket in self.tickets.items():
            self.add_icon(ticket)

        # Run the command periodically
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_icons)
        self.timer.start(2000)

    def add_icon(self, ticket):
        icon = Icon(QSystemTrayIcon(self.get_icon_for_ticket(ticket)))

        icon.menu = QMenu()
        exit_action = QAction("Exit", self.app)
        exit_action.triggered.connect(self.exit_app)
        icon.expires = QAction(f"Expires: {ticket.expires}")
        # expires.setEnabled(False)
        icon.menu.addAction(exit_action)
        icon.menu.addAction(icon.expires)
        icon.object.setContextMenu(icon.menu)

        icon.object.show()

        self.icons[ticket.principal] = icon

    @staticmethod
    def get_icon_for_ticket(ticket):
        if ticket.is_active():
            if ticket.principal in _icon_files:
                icon_name = _icon_files[ticket.principal]
            else:
                icon_name = _icon_files["other"]
        else:
            icon_name = _icon_files["inactive"]

        return QIcon(str(_DIR / icon_name))

    def update_icons(self):
        self.tickets = tickets_from_klist()

        for principal, icon in self.icons.items():
            if principal not in self.tickets:
                icon.object.hide()
            else:
                icon.object.show()

        for principal, ticket in self.tickets.items():
            if principal not in self.icons:
                self.add_icon(ticket)
            self.icons[principal].object.setIcon(self.get_icon_for_ticket(ticket))
            self.icons[principal].expires.setText(f"Expires: {ticket.expires}")

    def exit_app(self):
        for principal, icon in self.icons.items():
            icon.object.hide()
        sys.exit()

    def run(self):
        sys.exit(self.app.exec_())


if __name__ == "__main__":
    app = TrayApp()
    app.run()
