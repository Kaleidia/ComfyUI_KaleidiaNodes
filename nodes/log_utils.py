import os
import sys
import logging
import copy

def enable_windows_ansi():
    if sys.platform == 'win32':
        print("[Kaleidia Nodes] Console override ---------------------------------------------------------------")
        # 1. Force a blank command to 'wake up' the console
        os.system('') 
        
        # 2. Use ctypes to set the Virtual Terminal Processing flag
        import ctypes
        from ctypes import wintypes
        
        kernel32 = ctypes.windll.kernel32
        # -11 is the handle for Standard Output
        h_stdout = kernel32.GetStdHandle(-11)
        mode = wintypes.DWORD()
        
        if kernel32.GetConsoleMode(h_stdout, ctypes.byref(mode)):
            # 0x0004 is ENABLE_VIRTUAL_TERMINAL_PROCESSING
            mode.value |= 0x0004
            kernel32.SetConsoleMode(h_stdout, mode)

# Run it immediately upon import
enable_windows_ansi()

class LogColor:
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = "\033[95m"
    BOLD = '\033[1m'
    END = '\033[0m'

class ColoredFormatter(logging.Formatter):
    # Mapping log levels to your LogColor constants
    COLORS = {
        "DEBUG": LogColor.CYAN,     # For Pass/Depth info
        "INFO": LogColor.GREEN,     # For completion
        "WARNING": LogColor.YELLOW,  # For Gear shifts/Cache refresh
        "ERROR": LogColor.RED,
        "CRITICAL": LogColor.BOLD + LogColor.RED,
    }

    def format(self, record):
        log_record = copy.copy(record)
        color = self.COLORS.get(log_record.levelname, LogColor.END)
        # Format: [Prefix LEVEL] Message
        log_record.levelname = f"{LogColor.BOLD}{color}{log_record.levelname}{LogColor.END}"
        return super().format(log_record)

# Initialize the Logger
logger = logging.getLogger("Kaleidia Nodes")
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    # Customize your prefix here (e.g., [KN_SEQ])
    handler.setFormatter(ColoredFormatter(f"{LogColor.BOLD}[Kaleidia Nodes %(levelname)s]{LogColor.END} %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)