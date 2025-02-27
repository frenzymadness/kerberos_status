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
_re_expires = re.compile(
    r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}\s+(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\s+\S+@\S+"
)
_icon_files = {
    "redhat.com": _IMAGES / "key-red.png",
    "fedoraproject.org": _IMAGES / "key-blue.png",
    "other": _IMAGES / "key-yellow.png",
    "inactive": _IMAGES / "key-grey.png",
}


class Icon:
    def __init__(self, object, menu=None, expires=None):
        self.object = object
        self.menu = menu
        self.expires = expires


class Ticket:
    def __init__(self, principal, expires=None, is_renewable=False):
        self.principal = principal
        self.expires = expires
        self.is_renewable = is_renewable

    @classmethod
    def tickets_from_klist(cls):
        tickets = {}
        try:
            result = subprocess.run(["klist", "-A"], capture_output=True, text=True)
        except Exception as e:
            print(f"Error: {e}")

        output = result.stdout.strip()

        for line in output.splitlines():
            if line.startswith("Default principal:"):
                principal = line.split(":")[1].strip()
                tickets[principal] = cls(principal)
            elif m := re.match(_re_expires, line):
                tickets[principal].expires = datetime.strptime(
                    m.group(1), "%m/%d/%Y %H:%M:%S"
                )
            elif "renew until" in line:
                tickets[principal].is_renewable = True

        return tickets

    def is_active(self):
        return self.expires > datetime.now()

    def renew_if_possible(self):
        if self.is_renewable and self.is_active:
            try:
                subprocess.run(["kinit", "-R", self.principal])
            except Exception as e:
                print(f"ERROR: Cannot renew {self}, {e}")


class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.icons = {}

        self.tickets = Ticket.tickets_from_klist()

        for principal, ticket in self.tickets.items():
            self.add_icon(ticket)

        # Run the command periodically
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_icons)
        self.timer.start(60000)

    def add_icon(self, ticket):
        icon = Icon(QSystemTrayIcon(self.get_icon_for_ticket(ticket)))

        icon.menu = QMenu()
        icon.info = QAction(f"Principal: {ticket.principal}")
        icon.expires = QAction(f"Expires: {ticket.expires}")
        exit_action = QAction("Exit", self.app)
        exit_action.triggered.connect(self.exit_app)

        icon.menu.addAction(icon.info)
        icon.menu.addAction(icon.expires)
        icon.menu.addAction(exit_action)
        icon.object.setContextMenu(icon.menu)

        icon.object.show()

        self.icons[ticket.principal] = icon

    @staticmethod
    def get_icon_for_ticket(ticket):
        if ticket.is_active():
            for domain, icon_name in _icon_files.items():
                if domain in ticket.principal.lower():
                    return QIcon(str(_DIR / icon_name))
            return QIcon(str(_DIR / _icon_files["other"]))
        return QIcon(str(_DIR / _icon_files["inactive"]))

    def update_icons(self):
        self.tickets = Ticket.tickets_from_klist()

        for principal, icon in self.icons.items():
            if principal not in self.tickets:
                icon.object.hide()
            else:
                icon.object.show()

        for principal, ticket in self.tickets.items():
            ticket.renew_if_possible()
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
