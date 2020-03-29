from threading import Lock, Event
from queue import Queue
from typing import Dict, List

from rial.ParserState import ParserState
from rial.configuration import Configuration
from rial.util import _path_from_mod_name


class CompilationManager:
    files_to_compile: Queue
    files_compiled: Dict[str, Event]
    ps: ParserState
    object_files: List[str]
    lock: Lock
    config: Configuration

    def __init__(self):
        global _instance
        if _instance is not None:
            raise PermissionError()

    @staticmethod
    def init(config: Configuration):
        global _instance
        _instance = CompilationManager()
        _instance.files_to_compile = Queue()
        _instance.files_compiled = dict()
        _instance.ps = ParserState()
        _instance.object_files = list()
        _instance.lock = Lock()
        _instance.config = config

        return _instance

    @staticmethod
    def finish_file(path: str):
        with _instance.lock:
            if path in _instance.files_compiled:
                _instance.files_compiled[path].set()

    @staticmethod
    def request_module(mod_name: str) -> bool:
        """
        Adds a module with the name :mod_name: to the list of modules that need to be compiled.
        It then blocks until the module is compiled.
        :param mod_name:
        :return:
        """
        path = _path_from_mod_name(_instance.config.project_name, str(_instance.config.source_path), mod_name)
        is_compiling = False

        with _instance.lock:
            if path in _instance.files_compiled:
                is_compiling = True
            else:
                _instance.files_compiled[path] = Event()

        if is_compiling:
            return _instance.files_compiled[path].wait()

        _instance.files_to_compile.put(path)

        return _instance.files_compiled[path].wait()


_instance: CompilationManager = None
