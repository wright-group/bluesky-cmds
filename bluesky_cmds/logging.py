__all__ = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "getLogger",
    "setLevel",
]

from collections import defaultdict
import itertools
import logging

from qtpy import QtCore, QtGui, QtWidgets
from ._app import app
from .project.colors import colors

DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

logger_color_cycle = itertools.cycle(list(colors.values())[:10])

#
# Signals need to be contained in a QObject or subclass in order to be correctly
# initialized.
#
class Signaller(QtCore.QObject):
    signal = QtCore.Signal(str, logging.LogRecord)

class QtHandler(logging.Handler):
    def __init__(self, slotfunc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signaller = Signaller()
        self.signaller.signal.connect(slotfunc)

    def emit(self, record):
        s = self.format(record)
        self.signaller.signal.emit(s, record)

#
# Implement a simple UI for this cookbook example. This contains:
#
# * A read-only text edit window which holds formatted log messages
# * A button to clear the log window
#
# Adapted from https://docs.python.org/3/howto/logging-cookbook.html#a-qt-gui-for-logging
#
class LogWidget(QtWidgets.QWidget):

    COLORS = {
        logging.DEBUG: colors["comment"],
        logging.INFO: colors["blue"],
        logging.WARNING: colors["yellow"],
        logging.ERROR: colors["red"],
        logging.CRITICAL: colors["orange"],
    }
    LOGGER_COLORS = defaultdict(lambda: next(logger_color_cycle))

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.textedit = te = QtWidgets.QPlainTextEdit(self)
        # Set whatever the default monospace font is for the platform
        te.setStyleSheet(f"QPlainTextEdit{{background-color: {colors['background']}; color: {colors['text_light']};}}")
        f = QtGui.QFont('nosuchfont')
        f.setStyleHint(f.Monospace)
        te.setFont(f)
        te.setReadOnly(True)
        PB = QtWidgets.QPushButton
        self.clear_button = PB('Clear log window', self)

        # Lay out all the widgets
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(te)
        layout.addWidget(self.clear_button)

        # Connect the non-worker slots and signals
        self.clear_button.clicked.connect(self.clear_display)

    # The functions below update the UI and run in the main thread because
    # that's where the slots are set up

    def update_status(self, status, record):
        level_color = self.COLORS.get(record.levelno, 'white')
        logger_color = self.LOGGER_COLORS[record.name]
        s = f'<pre><font color="{level_color}">{record.levelname:10}</font><font color="{logger_color}">{record.name}:  </font>{status}</pre>'
        self.textedit.appendHtml(s)

    def clear_display(self):
        self.textedit.clear()

log_widget = LogWidget(app)

formatter = logging.Formatter(
    "{levelname} : {asctime} : {name} : {message}",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
    style="{",
)

_loggers = []
_default_level = logging.INFO


def getLogger(name=None, *, console=True):
    """Wrapper of `logging.getLogger` which sets the default formatter."""
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        if console:
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        ch = QtHandler(log_widget.update_status)
        logger.addHandler(ch)
        logger.setLevel(_default_level)
        _loggers.append(logger)
    return logger


def setLevel(level):
    global _default_level
    _default_level = level
    for log in _loggers:
        log.setLevel(level)
