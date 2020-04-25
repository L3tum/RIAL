from pathlib import Path
from queue import Queue
from threading import Lock, Event
from typing import Dict, List

from llvmlite.ir import Module, Function

from rial.codegen import CodeGen
from rial.configuration import Configuration


class CompilationManager:
    files_to_compile: Queue
    files_compiled: Dict[str, Event]
    modules: Dict[str, Module]
    cached_modules: List[str]
    lock: Lock
    config: Configuration
    codegen: CodeGen
    always_imported: List[str]
    builtin_types: Dict[str, Dict[str, List[Function]]]

    def __init__(self):
        raise PermissionError()

    @staticmethod
    def init(config: Configuration):
        CompilationManager.files_to_compile = Queue()
        CompilationManager.files_compiled = dict()
        CompilationManager.cached_modules = list()
        CompilationManager.lock = Lock()
        CompilationManager.config = config
        CompilationManager.modules = dict()
        CompilationManager.codegen = CodeGen(config.raw_opts.opt_level)
        CompilationManager.always_imported = list()
        CompilationManager.builtin_types = dict()

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
        path = CompilationManager.path_from_mod_name(mod_name)
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
        path = CompilationManager.path_from_mod_name(mod_name)
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

    @staticmethod
    def get_output_path(path: Path) -> Path:
        return CompilationManager.get_output_path_str(str(path))

    @staticmethod
    def get_output_path_str(path: str) -> Path:
        if path.startswith(str(CompilationManager.config.source_path)):
            return Path(
                path.replace(str(CompilationManager.config.source_path), str(CompilationManager.config.output_path)))

        if path.startswith(str(CompilationManager.config.rial_path)):
            path = path.split("/rial/")[-1]
            return CompilationManager.config.output_path.joinpath(path)

        return Path(path)

    @staticmethod
    def path_from_mod_name(mod_name: str) -> str:
        mod_name = mod_name.replace(':', '/') + ".rial"

        if mod_name.startswith(CompilationManager.config.project_name):
            mod_name = mod_name.replace(CompilationManager.config.project_name,
                                        str(CompilationManager.config.source_path))
        elif mod_name.startswith("rial"):
            mod_name = mod_name.replace("rial", str(CompilationManager.config.rial_path), 1)

        return mod_name

    @staticmethod
    def mod_name_from_path(path: str) -> str:
        s = path.strip('/').replace('.rial', '').replace('/', ':')
        return s

    @staticmethod
    def filename_from_path(path: str) -> str:
        """
        Replaces source path, rial path and cache path
        :param path:
        :return:
        """
        return path.replace(str(CompilationManager.config.source_path), "").replace(
            str(CompilationManager.config.rial_path), "").replace(str(CompilationManager.config.cache_path), "")
