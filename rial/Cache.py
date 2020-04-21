import os
from typing import Dict, Union

import jsonpickle as jsonpickle
from llvmlite.ir import Module

from rial.compilation_manager import CompilationManager
from rial.profiling import run_with_profiling, ExecutionStep
from rial.util import good_hash


class CachedModule:
    cache_path: str
    _module: Module
    hashed: str
    last_modified: float

    def __init__(self, cache_path: str, module: Module, hashed: str, last_modified: float):
        self.cache_path = cache_path
        self._module = module
        self.hashed = hashed
        self.last_modified = last_modified

    @property
    def module(self):
        if self._module is None:
            self._module = CompilationManager.codegen.load_module(self.cache_path)

        return self._module


class Cache:
    cached_modules: Dict[str, CachedModule]

    @staticmethod
    @run_with_profiling("cache/index.json", ExecutionStep.READ_CACHE)
    def load_cache():
        if CompilationManager.config.raw_opts.disable_cache:
            Cache.cached_modules = dict()
            return
        index = CompilationManager.config.cache_path.joinpath("index.json")

        if index.exists():
            with index.open("r") as file:
                Cache.cached_modules = jsonpickle.decode(file.read())
        else:
            Cache.cached_modules = dict()

    @staticmethod
    def cache_module(module: Module, src_path: str, cache_path: str, hashed: str, last_modified: float):
        Cache.cached_modules[src_path] = CachedModule(cache_path, module, hashed, last_modified)

    @staticmethod
    @run_with_profiling("cache/index.json", ExecutionStep.WRITE_CACHE)
    def save_cache():
        index = CompilationManager.config.cache_path.joinpath("index.json")

        if index.exists():
            os.remove(str(index))

        for key, cached_mod in Cache.cached_modules.items():
            cached_mod._module = None

        with index.open("w") as file:
            file.write(jsonpickle.encode(Cache.cached_modules))

    @staticmethod
    def get_cached_module(src_path: str) -> Union[None, str, Module]:
        if src_path in Cache.cached_modules:
            cached_module = Cache.cached_modules[src_path]

            # Check modification time
            if cached_module.last_modified == os.path.getmtime(src_path):
                return cached_module.module

            # Updated
            cached_module.last_modified = os.path.getmtime(src_path)

            # Check hash
            filename = CompilationManager.filename_from_path(src_path)
            with run_with_profiling(filename, ExecutionStep.READ_FILE):
                with open(src_path, "r") as file:
                    contents = file.read()

            with run_with_profiling(filename, ExecutionStep.HASH_FILE):
                hashed = good_hash(contents)

            if cached_module.hashed == hashed:
                return cached_module.module

            # Updated
            cached_module.hashed = hashed

            # Return the already read in file contents
            return contents
        return None
