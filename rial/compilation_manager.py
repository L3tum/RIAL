from pathlib import Path
from threading import Lock, Event
from queue import Queue
from typing import Dict

import os
from llvmlite.binding import ModuleRef

from rial.ParserState import ParserState
from rial.configuration import Configuration
from rial.util import _path_from_mod_name


class CompilationManager:
    files_to_compile: Queue
    files_compiled: Dict[str, Event]
    ps: ParserState
    modules: Dict[str, ModuleRef]
    lock: Lock
    config: Configuration

    def __init__(self):
        raise PermissionError()

    @staticmethod
    def init(config: Configuration):
        CompilationManager.files_to_compile = Queue()
        CompilationManager.files_compiled = dict()
        CompilationManager.ps = ParserState()
        CompilationManager.object_files = list()
        CompilationManager.lock = Lock()
        CompilationManager.config = config
        CompilationManager.modules = dict()

    @staticmethod
    def finish_file(path: str):
        if path in CompilationManager.files_compiled:
            CompilationManager.files_compiled[path].set()

    @staticmethod
    def check_module_already_compiled(mod_name: str) -> bool:
        """
        We check for `files_compiled` rather than the more sensible `modules` because
        `files_compiled` will always get the filename added even if compilation
        does not succeed.
        :param mod_name:
        :return:
        """
        path = _path_from_mod_name(CompilationManager.config.project_name, str(CompilationManager.config.source_path),
                                   mod_name)
        with CompilationManager.lock:
            if path in CompilationManager.files_compiled:
                CompilationManager.files_compiled[path].wait()

                return True

        return False

    @staticmethod
    def request_module(mod_name: str) -> bool:
        """
        Adds a module with the name :mod_name: to the list of modules that need to be compiled.
        It then blocks until the module is compiled.
        :param mod_name:
        :return:
        """
        path = _path_from_mod_name(CompilationManager.config.project_name, str(CompilationManager.config.source_path),
                                   mod_name)
        is_compiling = False

        with CompilationManager.lock:
            if path in CompilationManager.files_compiled:
                is_compiling = True
            else:
                CompilationManager.files_compiled[path] = Event()

        if is_compiling:
            return CompilationManager.files_compiled[path].wait()

        CompilationManager.files_to_compile.put(path)

        return CompilationManager.files_compiled[path].wait()

    @staticmethod
    def get_cache_path(path: Path) -> Path:
        return CompilationManager.get_cache_path_str(str(path))

    @staticmethod
    def get_cache_path_str(path: str) -> Path:
        if path.startswith(str(CompilationManager.config.source_path)):
            return Path(
                path.replace(str(CompilationManager.config.source_path), str(CompilationManager.config.cache_path)))

        if path.startswith(str(CompilationManager.config.rial_path)):
            path = path.split("/rial/")[-1]
            return CompilationManager.config.cache_path.joinpath(path)

        return Path(path)
