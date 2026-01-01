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
    Universal Debugging Utility with Python logging integration.
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
        
        # Configure Python logging
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        
        # Set up root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger("rhapi")
        
        if self.enabled:
            print(f"{self.HEADER}🐛 BugEater Active: Debug Mode ON{self.ENDC}")
            self.logger.debug("Debug mode enabled")

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
        """Standard info log."""
        self.logger.info(f"[{label}] {message}")
        
        if not self.enabled: return
        
        caller = self._get_caller()
        print(f"{self.CYAN}[{self._timestamp()}] {caller} | {label}: {self.ENDC}{message}")

    def success(self, message):
        """Green success message (Always prints, even if debug is off, unless forced)"""
        # Usually we want success messages visible in production too, 
        # but if you strictly want them hidden, add: if not self.enabled: return
        print(f"{self.GREEN}✅ {message}{self.ENDC}")

    def warn(self, message):
        """Yellow warning message."""
        self.logger.warning(message)
        
        if not self.enabled: return
        caller = self._get_caller()
        print(f"{self.WARNING}⚠️  [{caller}] WARNING: {message}{self.ENDC}")

    def error(self, message, exception=None):
        """Red error message. Prints full traceback if exception provided."""
        # Log to Python logger
        if exception:
            self.logger.error(f"{message}: {exception}", exc_info=True)
        else:
            self.logger.error(message)
        
        # Errors should usually print even in production
        caller = self._get_caller()
        print(f"{self.FAIL}❌ [{self._timestamp()}] {caller} ERROR: {message}{self.ENDC}")
        if exception:
            print(f"{self.FAIL}{traceback.format_exc()}{self.ENDC}")

    def section(self, title):
        """Creates a visual separator for logs."""
        if not self.enabled: return
        print(f"\n{self.HEADER}{'='*10} {title.upper()} {'='*10}{self.ENDC}")

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
        except Exception as e:
            print(f"{self.FAIL}Could not inspect data: {e}{self.ENDC}")
            print(data)

# Create a Singleton instance so we don't have to init it everywhere
bug = BugEater()
