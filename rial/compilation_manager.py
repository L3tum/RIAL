from pathlib import Path
from threading import Lock, Event
from typing import Dict, List

from rial.codegen import CodeGen
from rial.concept.ordered_set_queue import OrderedSetQueue
from rial.configuration import Configuration
from rial.metadata.RIALModule import RIALModule


class CompilationManager:
    files_to_compile: OrderedSetQueue
    files_compiled: Dict[str, Event]
    modules: Dict[str, RIALModule]
    cached_modules: List[str]
    compiled_lock: Lock
    config: Configuration
    codegen: CodeGen
    always_imported: List[str]

    def __init__(self):
        raise PermissionError()

    @staticmethod
    def init(config: Configuration):
        CompilationManager.files_to_compile = OrderedSetQueue()
        CompilationManager.files_compiled = dict()
        CompilationManager.cached_modules = list()
        CompilationManager.compiled_lock = Lock()
        CompilationManager.config = config
        CompilationManager.modules = dict()
        CompilationManager.codegen = CodeGen(config.raw_opts.opt_level)
        CompilationManager.always_imported = list()

    @staticmethod
    def finish_file(path: str):
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
        return CompilationManager.check_path_already_compiled(CompilationManager.path_from_mod_name(mod_name))

    @staticmethod
    def check_path_already_compiled(path: str) -> bool:
        return path in CompilationManager.files_compiled and CompilationManager.files_compiled[path].is_set()

    @staticmethod
    def wait_for_module_compiled(mod_name: str) -> bool:
        return CompilationManager.wait_for_path_compiled(CompilationManager.path_from_mod_name(mod_name))

    @staticmethod
    def wait_for_path_compiled(path: str) -> bool:
        if not path in CompilationManager.files_compiled:
            return False

        return CompilationManager.files_compiled[path].wait()

    @staticmethod
    def request_module(mod_name: str):
        """
        Adds a module with the name :mod_name: to the list of modules that need to be compiled.
        It then blocks until the module is compiled.
        :param mod_name:
        :return:
        """
        CompilationManager.request_file(CompilationManager.path_from_mod_name(mod_name))

    @staticmethod
    def request_file(path: str):
        with CompilationManager.compiled_lock:
            if not path in CompilationManager.files_compiled:
                CompilationManager.files_compiled[path] = Event()
                CompilationManager.files_to_compile.put(path)

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
        module_name = path.strip('/').replace('.rial', '').replace('/', ':')
        if module_name.startswith("builtin") or module_name.startswith("std"):
            module_name = f"rial:{module_name}"
        else:
            module_name = CompilationManager.config.project_name + ":" + module_name
        return module_name

    @staticmethod
    def filename_from_path(path: str) -> str:
        """
        Replaces source path, rial path and cache path
        :param path:
        :return:
        """
        return path.replace(str(CompilationManager.config.source_path), "").replace(
            str(CompilationManager.config.rial_path), "").replace(str(CompilationManager.config.cache_path), "")
