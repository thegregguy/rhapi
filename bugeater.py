import os
import json
import inspect
import datetime
import traceback
import logging
from dotenv import load_dotenv

# Load env to check for debug flag immediately
load_dotenv()

class BugEater:
    """
    Universal Debugging Utility with Python logging bridge.
    eats bugs for breakfast.
    """
    
    # ANSI Color Codes
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    def __init__(self):
        # check for string 'True' or '1'
        debug_env = os.getenv("DEBUG", "False").lower()
        self.enabled = debug_env in ["true", "1", "yes", "on"]
        
        # Setup Python logging
        self._setup_logging()
        
        if self.enabled:
            print(f"{self.HEADER}🐛 BugEater Active: Debug Mode ON{self.ENDC}")
            self.logger.debug("BugEater initialized in debug mode")
    
    def _setup_logging(self):
        """Setup Python logging with colored console handler"""
        self.logger = logging.getLogger("trader")
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            log_level = logging.DEBUG if self.enabled else logging.INFO
            self.logger.setLevel(log_level)
            
            # Console handler for colored output
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            
            # Simple format without colors for logging
            formatter = logging.Formatter('[%(asctime)s] %(name)s | %(levelname)s: %(message)s', datefmt='%H:%M:%S')
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)

    def _get_caller(self):
        """Finds the filename and line number of the script calling the debugger."""
        stack = inspect.stack()
        # Stack[0] is here, [1] is internal wrapper, [2] is usually the caller
        frame = stack[2]
        filename = os.path.basename(frame.filename)
        return f"{filename}:{frame.lineno}"

    def _timestamp(self):
        return datetime.datetime.now().strftime("%H:%M:%S")

    def log(self, message, label="INFO"):
        """Standard info log with Python logging bridge."""
        if not self.enabled: return
        
        caller = self._get_caller()
        print(f"{self.CYAN}[{self._timestamp()}] {caller} | {label}: {self.ENDC}{message}")
        self.logger.info(f"[{label}] {message}")

    def success(self, message):
        """Green success message (Always prints, even if debug is off)"""
        print(f"{self.GREEN}✅ {message}{self.ENDC}")
        self.logger.info(f"SUCCESS: {message}")

    def warn(self, message):
        """Yellow warning message with Python logging bridge."""
        if not self.enabled: return
        caller = self._get_caller()
        print(f"{self.WARNING}⚠️  [{caller}] WARNING: {message}{self.ENDC}")
        self.logger.warning(message)

    def error(self, message, exception=None):
        """Red error message with Python logging bridge. Prints full traceback if exception provided."""
        caller = self._get_caller()
        print(f"{self.FAIL}❌ [{self._timestamp()}] {caller} ERROR: {message}{self.ENDC}")
        
        if exception:
            tb_str = traceback.format_exc()
            print(f"{self.FAIL}{tb_str}{self.ENDC}")
            self.logger.error(f"{message}\n{tb_str}")
        else:
            self.logger.error(message)

    def section(self, title):
        """Creates a visual separator for logs."""
        if not self.enabled: return
        print(f"\n{self.HEADER}{'='*10} {title.upper()} {'='*10}{self.ENDC}")
        self.logger.info(f"{'='*10} {title.upper()} {'='*10}")

    def inspect(self, data, label="DATA INSPECTION"):
        """Pretty prints dictionaries or JSON objects."""
        if not self.enabled: return
        
        caller = self._get_caller()
        try:
            if isinstance(data, str):
                # Try to parse string as json just in case
                try: data = json.loads(data)
                except: pass
            
            pretty = json.dumps(data, indent=2, default=str)
            print(f"\n{self.BLUE}🧐 [{caller}] {label}:{self.ENDC}")
            print(f"{pretty}\n")
            self.logger.debug(f"[{label}] {pretty}")
        except Exception as e:
            print(f"{self.FAIL}Could not inspect data: {e}{self.ENDC}")
            print(data)
            self.logger.error(f"Could not inspect data: {e}")

# Create a Singleton instance so we don't have to init it everywhere
bug = BugEater()
