import os
import threading
import traceback
from multiprocessing.pool import ThreadPool
from os import listdir
from os.path import isfile, join
from pathlib import Path
from queue import Empty
from typing import List, Dict

from llvmlite.binding import ModuleRef
from llvmlite.ir import Module

from rial.ASTVisitor import ASTVisitor
from rial.Cache import Cache
from rial.DesugarTransformer import DesugarTransformer
from rial.FunctionDeclarationTransformer import FunctionDeclarationTransformer
from rial.ParserState import ParserState
from rial.PrimitiveASTTransformer import PrimitiveASTTransformer
from rial.StructDeclarationTransformer import StructDeclarationTransformer
from rial.compilation_manager import CompilationManager
from rial.concept.Postlexer import Postlexer
from rial.concept.compilation_unit import CompilationUnit
from rial.concept.parser import Lark_StandAlone
from rial.linking.linker import Linker
from rial.log import log_fail
from rial.platform_support.Platform import Platform
from rial.profiling import run_with_profiling, ExecutionStep

global exceptions


def compiler():
    global exceptions
    exceptions = False

    if not CompilationManager.config.raw_opts.disable_cache:
        Cache.load_cache()

    if CompilationManager.config.raw_opts.file is not None:
        path = Path(CompilationManager.config.raw_opts.file)
    else:
        path = CompilationManager.config.rial_path.joinpath("builtin").joinpath("start.rial")
    # path = source_path.joinpath("main.rial")

    if not path.exists():
        raise FileNotFoundError(str(path))

    # Start threads
    threads = list()
    for i in range(CompilationManager.config.raw_opts.compile_units):
        t = threading.Thread(target=compile_file)
        t.daemon = True
        t.start()
        threads.append(t)

    # Collect all always imported paths
    builtin_path = str(CompilationManager.config.rial_path.joinpath("builtin").joinpath("always_imported"))
    for file in [join(builtin_path, f) for f in listdir(builtin_path) if isfile(join(builtin_path, f))]:
        CompilationManager.request_file(file)
        module_name = CompilationManager.mod_name_from_path(CompilationManager.filename_from_path(str(file)))
        CompilationManager.always_imported.append(module_name)

    # Request main file
    CompilationManager.request_file(path)

    # Wait on all files compiled
    CompilationManager.files_to_compile.join()
    CompilationManager.phase_two_queue.join()

    if exceptions:
        return

    if not CompilationManager.config.raw_opts.disable_cache:
        Cache.save_cache()

    modules: Dict[str, ModuleRef] = dict()

    for key, mod in CompilationManager.modules.items():
        if not CompilationManager.config.raw_opts.disable_cache:
            cache_path = str(CompilationManager.get_cache_path_str(key)).replace(".rial", ".cache")
            if not Path(cache_path).exists():
                CompilationManager.codegen.save_module(mod, cache_path)

        with run_with_profiling(CompilationManager.filename_from_path(key), ExecutionStep.COMPILE_MOD):
            try:
                modules[key] = CompilationManager.codegen.compile_ir(mod)
            except Exception as e:
                log_fail(f"Exception when compiling module {mod.name}")
                log_fail(e)
                return

    object_files: List[str] = list()
    CompilationManager.codegen.generate_final_modules(list(modules.values()))

    for path in list(modules.keys()):
        mod = modules[path]

        if CompilationManager.config.raw_opts.print_ir:
            ir_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".ll")
            CompilationManager.codegen.save_ir(ir_file, mod)

        if CompilationManager.config.raw_opts.print_asm:
            asm_file = str(CompilationManager.get_cache_path_str(path)).replace(".rial", ".asm")
            CompilationManager.codegen.save_assembly(asm_file, mod)

        if not CompilationManager.config.raw_opts.use_object_files:
            llvm_bitcode_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".o")
            CompilationManager.codegen.save_llvm_bitcode(llvm_bitcode_file, mod)
            object_files.append(llvm_bitcode_file)
        else:
            object_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".o")
            CompilationManager.codegen.save_object(object_file, mod)
            object_files.append(object_file)

    with run_with_profiling(CompilationManager.config.project_name, ExecutionStep.LINK_EXE):
        exe_path = str(CompilationManager.config.bin_path.joinpath(
            f"{CompilationManager.config.project_name}{Platform.get_exe_file_extension()}"))

        Linker.link_files(object_files, exe_path, CompilationManager.config.raw_opts.print_link_command,
                          CompilationManager.config.raw_opts.strip)


def finish_file_phase_one():
    CompilationManager.files_to_compile.task_done()


def finish_file_phase_two(path):
    CompilationManager.finish_file(path)
    CompilationManager.phase_two_queue.task_done()


def finish_file_overall(path):
    finish_file_phase_one()
    finish_file_phase_two(path)


def compile_file():
    global exceptions
    while True:
        try:
            compile_phase_one()
            compile_phase_two()
        except Exception as e:
            log_fail("Internal Compiler Error: ")
            log_fail(traceback.format_exc())
            exceptions = True
            finish_file_overall(e.path)


def compile_phase_one():
    global exceptions
    path = None
    try:
        try:
            path = str(CompilationManager.files_to_compile.get(timeout=0.01))
        except Empty:
            return

        module = None
        last_modified = None

        if not Path(path).exists():
            log_fail(f"Could not find {path}")
            finish_file_overall(path)
            return

        # Check beforehand because we'd rather compile it once too often than once too less
        if not CompilationManager.config.raw_opts.disable_cache:
            last_modified = os.path.getmtime(path)
            module = Cache.get_cached_module(path)

            if isinstance(module, Module):
                dependency_invalidated = False

                # Check for dependencies
                for mod in module.get_dependencies():
                    if CompilationManager.check_module_already_compiled(mod):
                        if not mod in CompilationManager.cached_modules:
                            dependency_invalidated = True
                            CompilationManager.request_module(mod)

                # If a dependency got invalidated
                # we need to compile this module again as well
                if not dependency_invalidated:
                    CompilationManager.modules[str(path)] = module
                    CompilationManager.cached_modules.append(module.name)
                    finish_file_overall(path)
                    return
                else:
                    module = None
            elif isinstance(module, str):
                contents = module

        file = CompilationManager.filename_from_path(path)

        # If module is None then the Cache was either disabled or has never seen the file before.
        # Ergo we need to all the work.
        if module is None:
            with run_with_profiling(file, ExecutionStep.READ_FILE):
                with open(path, "r") as src:
                    contents = src.read()

        # Cache is invalid. Delete the file
        cache_path = str(CompilationManager.get_cache_path_str(path)).replace(".rial", ".cache")
        if Path(cache_path).exists():
            os.remove(cache_path)

        module_name = CompilationManager.mod_name_from_path(file)
        module = CompilationManager.codegen.get_module(module_name, file.split('/')[-1],
                                                       str(CompilationManager.config.source_path))
        ParserState.reset_usings()
        ParserState.usings().extend(CompilationManager.always_imported)

        # Remove the current module in case it's in the always imported list
        if module_name in ParserState.usings():
            ParserState.usings().remove(module_name)
        ParserState.set_module(module)
        primitive_transformer = PrimitiveASTTransformer()
        desugar_transformer = DesugarTransformer()
        parser = Lark_StandAlone(postlex=Postlexer())

        # Parse the file
        with run_with_profiling(file, ExecutionStep.PARSE_FILE):
            try:
                ast = parser.parse(contents)
            except Exception as e:
                log_fail(f"Exception when parsing {file}")
                log_fail(e)
                finish_file_overall(path)
                exceptions = True
                return

        if CompilationManager.config.raw_opts.print_tokens:
            print(ast.pretty())

        # Generate primitive IR (things we don't need other modules for)
        with run_with_profiling(file, ExecutionStep.GEN_IR):
            ast = primitive_transformer.transform(ast)
            ast = desugar_transformer.transform(ast)

        # Put into phase two queue
        CompilationManager.compilation_units[path] = CompilationUnit(ParserState.module(), ParserState.usings(),
                                                                     last_modified, ast)
        CompilationManager.phase_two_queue.put(path)
        finish_file_phase_one()
    except Exception as e:
        e.path = path
        raise e


def compile_phase_two():
    global exceptions
    path = None
    try:
        try:
            path = str(CompilationManager.phase_two_queue.get(timeout=0.01))
        except Empty:
            return

        if not path in CompilationManager.compilation_units:
            log_fail("Could not find compilation unit.")
            finish_file_phase_two(path)
            return

        unit = CompilationManager.compilation_units[path]

        # Check if all dependencies are compiled
        all_compiled = True
        for using in unit.usings:
            if CompilationManager.check_module_still_compiling(using):
                all_compiled = False
                break

        if not all_compiled:
            CompilationManager.phase_two_queue.task_done()
            CompilationManager.phase_two_queue.put(path)
            return

        del CompilationManager.compilation_units[path]
        ParserState.reset_usings()
        ParserState.usings().extend(unit.usings)
        ParserState.set_module(unit.module)

        file = CompilationManager.filename_from_path(path)
        function_declaration_transformer = FunctionDeclarationTransformer()
        struct_declaration_transformer = StructDeclarationTransformer()
        transformer = ASTVisitor()

        with run_with_profiling(file, ExecutionStep.GEN_IR):
            ast = struct_declaration_transformer.transform(unit.ast)

            if ast is not None:
                ast = function_declaration_transformer.visit(ast)

            # Declarations are all already collected so we can move on.
            CompilationManager.modules[str(path)] = ParserState.module()
            CompilationManager.finish_file(path)

            if ast is not None:
                transformer.visit(ast)

        if not CompilationManager.config.raw_opts.disable_cache:
            cache_path = str(CompilationManager.get_cache_path_str(path)).replace(".rial", ".cache")
            Cache.cache_module(ParserState.module(), path, cache_path, unit.last_modified)
        finish_file_phase_two(path)
    except Exception as e:
        e.path = path
        raise e
