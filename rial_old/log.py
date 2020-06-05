import sys

from colorama import Fore, Style


def log_success(message: str):
    print(f"{Style.BRIGHT}{Fore.GREEN}{message}{Style.RESET_ALL}")


def log_fail(message: str):
    print(f"{Style.BRIGHT}{Fore.RED}{message}{Style.RESET_ALL}", file=sys.stderr)


def log_warn(message: str):
    print(f"{Style.BRIGHT}{Fore.RED}WARNING: {message}{Style.RESET_ALL}")

def log_warn_short(message: str):
    print(f"{Style.BRIGHT}{Fore.RED}{message}{Style.RESET_ALL}")