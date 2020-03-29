from contextlib import contextmanager
from threading import Lock
from typing import Dict, Optional, List

from rial.LLVMFunction import LLVMFunction


class ParserState(object):
    functions: Dict[str, LLVMFunction]
    implemented_functions: List[str]
    lock: Lock

    def __init__(self):
        self.functions = dict()
        self.implemented_functions = list()
        self.lock = Lock()

    def get_named_function(self, name: str) -> Optional[LLVMFunction]:
        ty = None

        with self.lock:
            if name in self.functions:
                ty = self.functions[name]

        return ty

    @contextmanager
    def lock_and_search_named_function(self, name: str) -> Optional[LLVMFunction]:
        ty = None

        with self.lock:
            if name in self.functions:
                ty = self.functions[name]
            yield ty

        return ty
