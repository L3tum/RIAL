import os
from os import listdir
from os.path import join, isfile
from pathlib import Path
from typing import Dict, List

from llvmlite import ir
from llvmlite.binding import ModuleRef

from rial.Cache import Cache
from rial.codegen import CodeGen
from rial.concept.combined_transformer import CombinedTransformer
from rial.concept.parser import Lark_StandAlone
from rial.configuration import Configuration
from rial.ir.RIALModule import RIALModule
from rial.linking.linker import Linker
from rial.platform_support.Platform import Platform
from rial.profiling import run_with_profiling, ExecutionStep
from rial.util.log import log_fail


class CompilationManager:
    modules: Dict[str, RIALModule]
    cached_modules: List[str]
    config: Configuration
    codegen: CodeGen
    always_imported: List[str]
    parser: Lark_StandAlone
    current_module = RIALModule

    def __init__(self):
        raise PermissionError()

    @staticmethod
    def init(config: Configuration):
        Cache.init(config.cache_path, config.raw_opts.disable_cache)
        CompilationManager.cached_modules = list()
        CompilationManager.config = config
        CompilationManager.modules = dict()
        CompilationManager.codegen = CodeGen(config.raw_opts.opt_level, config.raw_opts.disable_opt)
        CompilationManager.always_imported = list()

        if not CompilationManager.config.raw_opts.disable_cache:
            Cache.load_cache()

        # Reset global context
        ir.context.global_context = ir.Context()

        # Setup parser
        from rial.transformer.Postlexer import Postlexer
        CompilationManager.parser = Lark_StandAlone(postlex=Postlexer())

    @staticmethod
    def fini():
        if not CompilationManager.config.raw_opts.disable_cache:
            Cache.save_cache()

    @staticmethod
    def compiler():
        # Collect all always imported paths
        CompilationManager._collect_always_imported_paths()

        # Request main file
        if CompilationManager.config.raw_opts.file is not None:
            path = Path(CompilationManager.config.raw_opts.file)
        else:
            path = CompilationManager.config.rial_path.joinpath("startup").joinpath("start.rial")
        if not path.exists():
            raise FileNotFoundError(str(path))
        CompilationManager._compile_file(str(path))

        modules: Dict[str, ModuleRef] = dict()

        for key, mod in CompilationManager.modules.items():
            path = CompilationManager.path_from_mod_name(key)

            if not CompilationManager.config.raw_opts.disable_cache:
                cache_path = str(CompilationManager.get_cache_path_str(path)).replace(".rial", ".cache")
                if not Path(cache_path).exists():
                    CompilationManager.codegen.save_module(mod, cache_path)

            with run_with_profiling(CompilationManager.filename_from_path(path), ExecutionStep.COMPILE_MOD):
                try:
                    modules[path] = CompilationManager.codegen.compile_ir(mod)
                except Exception as e:
                    import traceback
                    log_fail(f"Exception when compiling module {mod.name}")
                    log_fail(e)
                    log_fail(traceback.format_exc())
                    return

        object_files: List[str] = list()
        CompilationManager.codegen.generate_final_modules(list(modules.values()))

        for path in list(modules.keys()):
            mod = modules[path]

            if CompilationManager.config.raw_opts.print_ir:
                ir_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".ll")
                if CompilationManager._check_needs_output(mod.name, ir_file):
                    CompilationManager.codegen.save_ir(ir_file, mod)

            if CompilationManager.config.raw_opts.print_asm:
                asm_file = str(CompilationManager.get_cache_path_str(path)).replace(".rial", ".asm")
                if CompilationManager._check_needs_output(mod.name, asm_file):
                    CompilationManager.codegen.save_assembly(asm_file, mod)

            if not CompilationManager.config.raw_opts.use_object_files:
                llvm_bitcode_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".o")
                if CompilationManager._check_needs_output(mod.name, llvm_bitcode_file):
                    CompilationManager.codegen.save_llvm_bitcode(llvm_bitcode_file, mod)
                object_files.append(llvm_bitcode_file)
            else:
                object_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".o")
                if CompilationManager._check_needs_output(mod.name, object_file):
                    CompilationManager.codegen.save_object(object_file, mod)
                object_files.append(object_file)

        with run_with_profiling(CompilationManager.config.project_name, ExecutionStep.LINK_EXE):
            exe_path = str(CompilationManager.config.bin_path.joinpath(
                f"{CompilationManager.config.project_name}{Platform.get_exe_file_extension()}"))

            Linker.link_files(object_files, exe_path, CompilationManager.config.raw_opts.print_link_command,
                              CompilationManager.config.raw_opts.strip)

    @staticmethod
    def _compile_file(path: str):
        mod_name = CompilationManager.mod_name_from_path(path)
        filename = CompilationManager.filename_from_path(path)
        module = CompilationManager.codegen.get_module(mod_name, filename, path.replace(filename, ""))
        old_current_module = CompilationManager.current_module
        CompilationManager.current_module = module

        # Extend the dependencies with the always_imported things, unless the module itself is part of that group
        if not mod_name.startswith("rial:builtin:"):
            for dependency in CompilationManager.always_imported:
                module.dependencies[dependency] = dependency

        with run_with_profiling(filename, ExecutionStep.READ_FILE):
            with open(path, "r") as file:
                contents = file.read()

        # Parsing
        with run_with_profiling(filename, ExecutionStep.PARSE_FILE):
            try:
                ast = CompilationManager.parser.parse(contents)
            except Exception as e:
                log_fail(f"Exception when parsing {filename}")
                log_fail(e)
                return e

        if CompilationManager.config.raw_opts.print_tokens:
            print(ast.pretty())

        # Generate IR
        with run_with_profiling(filename, ExecutionStep.GEN_IR):
            from rial.transformer.DesugarTransformer import DesugarTransformer
            ast = DesugarTransformer(module).transform(ast)

            if ast is not None:
                from rial.transformer.StructDeclarationTransformer import StructDeclarationTransformer
                ast = StructDeclarationTransformer(module).visit(ast)

            if ast is not None:
                from rial.transformer.FunctionDeclarationTransformer import FunctionDeclarationTransformer
                ast = FunctionDeclarationTransformer(module).visit(ast)

            if ast is not None:
                from rial.transformer.MainTransformer import MainTransformer
                from rial.transformer.BuiltinTransformer import BuiltinTransformer
                from rial.transformer.LoopTransformer import LoopTransformer
                from rial.transformer.StandardOperationsTransformer import StandardOperationsTransformer
                from rial.transformer.FunctionCallTransformer import FunctionCallTransformer
                combined_transformer = CombinedTransformer()
                combined_transformer += FunctionCallTransformer()
                combined_transformer += BuiltinTransformer()
                combined_transformer += LoopTransformer()
                combined_transformer += StandardOperationsTransformer()
                combined_transformer += MainTransformer()
                for transformer in combined_transformer.transformers:
                    from rial.transformer.BaseTransformer import BaseTransformer
                    transformer: BaseTransformer
                    transformer.combined_transformer = combined_transformer

                from rial.transformer.GlobalDeclarationTransformer import GlobalDeclarationTransformer
                global_declaration_transformer = GlobalDeclarationTransformer()
                global_declaration_transformer.main_transformer = combined_transformer
                ast = global_declaration_transformer.transform(ast)

                if ast is not None:
                    ast = combined_transformer.visit(ast)

                del combined_transformer

        CompilationManager.modules[mod_name] = module
        CompilationManager.current_module = old_current_module

    @staticmethod
    def _collect_always_imported_paths():
        builtin_path = str(CompilationManager.config.rial_path.joinpath("builtin"))
        for file in [join(builtin_path, f) for f in listdir(builtin_path) if isfile(join(builtin_path, f))]:
            module_name = CompilationManager.mod_name_from_path(CompilationManager.filename_from_path(str(file)))
            CompilationManager.always_imported.append(module_name)
            CompilationManager._compile_file(file)

    @staticmethod
    def _check_cache(path: str) -> int:
        """
        Checks the Cache subsystem. Can be disabled as well, in which case it just returns 0.
        If the cache is invalid then it setups the cache again with the currently last modified time.
        If a dependency is invalid it returns 0.
        If dependencies haven't been compiled, yet, it returns -1 to signal a requeue. The requeue has already been done.
        :param path:
        :return:
        """
        if CompilationManager.config.raw_opts.disable_cache:
            return 0

        last_modified = os.path.getmtime(path)
        module = Cache.get_cached_module(path)

        if module is None:
            # Setup module for last_modified to be saved
            Cache.cache_module(None, path, str(CompilationManager.get_cache_path_str(path)), last_modified)
            return 0

        dependency_invalid = False
        request_recompilation = list()
        for dependency in module.dependencies:
            if CompilationManager.check_module_already_compiled(dependency):
                if dependency not in CompilationManager.cached_modules:
                    dependency_invalid = True
            else:
                request_recompilation.append(dependency)

        # Request compilation of dependencies
        for dependency in request_recompilation:
            CompilationManager.request_module(dependency)

        # If a dependency was already invalid we don't need to check again
        if dependency_invalid:
            return 0

        # If no dependency was invalid, yet, check again.
        if len(request_recompilation) > 0:
            return CompilationManager._check_cache(path)

        CompilationManager.cached_modules.append(module.name)
        return 1

    @staticmethod
    def check_module_already_compiled(mod_name: str) -> bool:
        """
        We check for `files_compiled` rather than the more sensible `modules` because
        `files_compiled` will always get the filename added even if compilation
        does not succeed.
        :param mod_name:
        :return:
        """
        return mod_name in CompilationManager.modules

    @staticmethod
    def check_path_already_compiled(path: str) -> bool:
        return CompilationManager.check_module_already_compiled(CompilationManager.mod_name_from_path(path))

    @staticmethod
    def request_module(mod_name: str):
        """
        Adds a module with the name :mod_name: to the list of modules that need to be compiled.
        It then blocks until the module is compiled.
        :param mod_name:
        :return:
        """
        if mod_name.startswith("builtin") or mod_name.startswith("core") or mod_name.startswith(
                "std") or mod_name.startswith("startup"):
            mod_name = f"rial:{mod_name}"
        if mod_name not in CompilationManager.modules:
            CompilationManager._compile_file(CompilationManager.path_from_mod_name(mod_name))

    @staticmethod
    def request_file(path: str):
        return CompilationManager.request_module(CompilationManager.mod_name_from_path(path))

    @staticmethod
    def get_cache_path(path: Path) -> Path:
        return CompilationManager.get_cache_path_str(str(path))

    @staticmethod
    def get_cache_path_str(path: str) -> Path:
        if path.startswith(str(CompilationManager.config.source_path)):
            return Path(
                path.replace(str(CompilationManager.config.source_path), str(CompilationManager.config.cache_path)))

        if path.startswith(str(CompilationManager.config.rial_path)):
            path = path.split("/std/")[-1]
            return CompilationManager.config.cache_path.joinpath("rial").joinpath(path)

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
            path = path.split("/std/")[-1]
            return CompilationManager.config.output_path.joinpath("rial").joinpath(path)

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
        path = path.replace(str(CompilationManager.config.source_path), "").replace(
            str(CompilationManager.config.rial_path), "")
        module_name = path.strip('/').replace('.rial', '').replace('/', ':')
        if module_name.startswith("builtin") or module_name.startswith("std") or module_name.startswith(
                "startup") or module_name.startswith("core"):
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

    @staticmethod
    def _check_needs_output(module_name: str, path: str):
        return not (module_name in CompilationManager.cached_modules and Path(path).exists())
