import logging
import sys
from PyQt6.QtCore import QObject, pyqtSignal, QCoreApplication

class LogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        if QCoreApplication.instance():
            msg = self.format(record)
            self.signal.emit(msg)

class Logger(QObject):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("UniversalMacroCreator")
        self.logger.setLevel(logging.DEBUG)
        self.enabled = True
        
        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # Qt Signal handler
        qh = LogHandler(self.log_signal)
        qh.setFormatter(formatter)
        self.logger.addHandler(qh)

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def info(self, msg):
        if self.enabled:
            self.logger.info(msg)

    def error(self, msg):
        if self.enabled:
            self.logger.error(msg)

    def debug(self, msg):
        if self.enabled:
            self.logger.debug(msg)

    def warning(self, msg):
        if self.enabled:
            self.logger.warning(msg)

# Global logger instance
app_logger = Logger()
