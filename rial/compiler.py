import concurrent.futures
import os
import traceback
from os import listdir
from os.path import isfile, join
from pathlib import Path
from queue import Empty
from typing import List, Dict

from llvmlite.binding import ModuleRef
from llvmlite.ir import context

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


def check_needs_output(module_name: str, path: str):
    return not (module_name in CompilationManager.cached_modules and Path(path).exists())


def compiler():
    global exceptions
    exceptions = False

    if not CompilationManager.config.raw_opts.disable_cache:
        Cache.load_cache()

    if CompilationManager.config.raw_opts.file is not None:
        path = Path(CompilationManager.config.raw_opts.file)
    else:
        path = CompilationManager.config.rial_path.joinpath("builtin").joinpath("start.rial")

    if not path.exists():
        raise FileNotFoundError(str(path))

    context.global_context.scope._useset.clear()
    context.global_context.identified_types.clear()

    # Collect all always imported paths
    builtin_path = str(CompilationManager.config.rial_path.joinpath("builtin").joinpath("always_imported"))
    for file in [join(builtin_path, f) for f in listdir(builtin_path) if isfile(join(builtin_path, f))]:
        CompilationManager.request_file(file)
        module_name = CompilationManager.mod_name_from_path(CompilationManager.filename_from_path(str(file)))
        CompilationManager.always_imported.append(module_name)

    # Request main file
    CompilationManager.request_file(str(path))

    if CompilationManager.config.raw_opts.profile_gil:
        import gil_load
        gil_load.init()
        gil_load.start()

    futures = list()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        while True:
            for future in futures:
                if future.done():
                    futures.remove(future)

            try:
                # This timeout is so small, it shouldn't matter.
                # However it serves a crucial role in regards to Python's GIL.
                # Setting this on a higher timeout obviously means that there may be some excessive time spent waiting
                # for nothing to appear.
                # BUT, setting it to non-blocking means that the GIL never gives any of the compilation threads priority
                # as well as holding up the internal threading.Lock(s).
                # So setting this timeout so small means not much time is spent waiting for nothing, but it gives other
                # things the opportunity to get control of the GIL and execute.
                path = CompilationManager.files_to_compile.get(timeout=0.01)
                future = executor.submit(compile_file, path)
                futures.append(future)
            except Empty:
                pass

            if len(futures) == 0 and CompilationManager.files_to_compile.empty():
                break
        executor.shutdown(True)

    CompilationManager.files_to_compile.join()

    if CompilationManager.config.raw_opts.profile_gil:
        import gil_load
        gil_load.stop()
        print(gil_load.format(gil_load.get()))

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
                log_fail(traceback.format_exc())
                return

    object_files: List[str] = list()
    CompilationManager.codegen.generate_final_modules(list(modules.values()))

    for path in list(modules.keys()):
        mod = modules[path]

        if CompilationManager.config.raw_opts.print_ir:
            ir_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".ll")
            if check_needs_output(mod.name, ir_file):
                CompilationManager.codegen.save_ir(ir_file, mod)

        if CompilationManager.config.raw_opts.print_asm:
            asm_file = str(CompilationManager.get_cache_path_str(path)).replace(".rial", ".asm")
            if check_needs_output(mod.name, asm_file):
                CompilationManager.codegen.save_assembly(asm_file, mod)

        if not CompilationManager.config.raw_opts.use_object_files:
            llvm_bitcode_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".o")
            if check_needs_output(mod.name, llvm_bitcode_file):
                CompilationManager.codegen.save_llvm_bitcode(llvm_bitcode_file, mod)
            object_files.append(llvm_bitcode_file)
        else:
            object_file = str(CompilationManager.get_output_path_str(path)).replace(".rial", ".o")
            if check_needs_output(mod.name, object_file):
                CompilationManager.codegen.save_object(object_file, mod)
            object_files.append(object_file)

    with run_with_profiling(CompilationManager.config.project_name, ExecutionStep.LINK_EXE):
        exe_path = str(CompilationManager.config.bin_path.joinpath(
            f"{CompilationManager.config.project_name}{Platform.get_exe_file_extension()}"))

        Linker.link_files(object_files, exe_path, CompilationManager.config.raw_opts.print_link_command,
                          CompilationManager.config.raw_opts.strip)


def check_cache(path: str) -> bool:
    if CompilationManager.config.raw_opts.disable_cache:
        return False

    module = Cache.get_cached_module(path)

    if module is None:
        return False

    dependency_invalid = False
    request_recompilation = list()
    with CompilationManager.compiled_lock:
        for dependency in module.dependencies:
            # If dependency has been compiled
            if CompilationManager.check_module_already_compiled(dependency):
                # But not cached, then it's invalid and we need to recompile
                if not dependency in CompilationManager.cached_modules:
                    dependency_invalid = True
            # If it has not been compiled then we request it
            else:
                request_recompilation.append(dependency)

    for dependency in request_recompilation:
        CompilationManager.request_module(dependency)

    for dependency in request_recompilation:
        CompilationManager.wait_for_module_compiled(dependency)

    if dependency_invalid:
        return False

    # Check cache again
    if len(request_recompilation) > 0:
        return check_cache(path)

    CompilationManager.modules[path] = module

    for struct in module.structs:
        context.global_context.get_identified_type(struct.name)
        context.global_context.identified_types[struct.name] = struct

    for key in module.builtin_type_methods.keys():
        if not key in ParserState.builtin_types:
            ParserState.builtin_types[key] = dict()
        for fun in module.builtin_type_methods[key]:
            ParserState.builtin_types[key][fun] = next((func for func in module.functions if func.name == func),
                                                       None)

    with CompilationManager.compiled_lock:
        CompilationManager.cached_modules.append(module.name)

    return True


def compile_file(path: str):
    global exceptions
    try:
        filename = CompilationManager.filename_from_path(path)
        unit = CompilationManager.get_compile_unit_if_exists(path)
        ParserState.reset_usings()

        if unit is None:
            last_modified = os.path.getmtime(path)

            if check_cache(path):
                CompilationManager.finish_file(path)
                CompilationManager.files_to_compile.task_done()
                return

            module_name = CompilationManager.mod_name_from_path(filename)
            module = CompilationManager.codegen.get_module(module_name, filename,
                                                           str(CompilationManager.config.source_path))
            ParserState.set_module(module)

            if not ParserState.module().name.startswith("rial:builtin:always_imported"):
                ParserState.usings().extend(CompilationManager.always_imported)

            # Remove the current module in case it's in the always imported list
            if module_name in ParserState.usings():
                ParserState.usings().remove(module_name)

            with run_with_profiling(filename, ExecutionStep.READ_FILE):
                with open(path, "r") as file:
                    contents = file.read()

            desugar_transformer = DesugarTransformer()
            primitive_transformer = PrimitiveASTTransformer()
            parser = Lark_StandAlone(postlex=Postlexer())

            # Parse the file
            with run_with_profiling(filename, ExecutionStep.PARSE_FILE):
                try:
                    ast = parser.parse(contents)
                except Exception as e:
                    log_fail(f"Exception when parsing {filename}")
                    log_fail(e)
                    exceptions = True
                    CompilationManager.finish_file(path)
                    CompilationManager.files_to_compile.task_done()
                    return

            if CompilationManager.config.raw_opts.print_tokens:
                print(ast.pretty())

            # Generate primitive IR (things we don't need other modules for)
            with run_with_profiling(filename, ExecutionStep.GEN_IR):
                ast = desugar_transformer.transform(ast)
                ast = primitive_transformer.transform(ast)

            unit = CompilationUnit(ParserState.module(), ParserState.usings(), last_modified, ast)
        else:
            last_modified = unit.last_modified
            ParserState.usings().extend(unit.usings)
            ParserState.set_module(unit.module)

            ast = unit.ast

        # Check if all dependencies are compiled
        wait_on_modules = list()
        with run_with_profiling(filename, ExecutionStep.WAIT_DEPENDENCIES):
            for using in unit.usings:
                if not CompilationManager.check_module_already_compiled(using):
                    CompilationManager.request_module(using)
                    wait_on_modules.append(using)

            for using in wait_on_modules:
                CompilationManager.wait_for_module_compiled(using)

        function_declaration_transformer = FunctionDeclarationTransformer()
        struct_declaration_transformer = StructDeclarationTransformer()
        transformer = ASTVisitor()

        with run_with_profiling(filename, ExecutionStep.GEN_IR):
            ast = struct_declaration_transformer.transform(ast)

            if ast is not None:
                ast = function_declaration_transformer.visit(ast)

            # Declarations are all already collected so we can move on.
            CompilationManager.modules[str(path)] = ParserState.module()
            CompilationManager.finish_file(path)

            if ast is not None:
                transformer.visit(ast)

        cache_path = str(CompilationManager.get_cache_path_str(path)).replace(".rial", ".cache")
        if Path(cache_path).exists() and CompilationManager.config.raw_opts.disable_cache:
            os.remove(cache_path)
        elif not CompilationManager.config.raw_opts.disable_cache:
            Cache.cache_module(ParserState.module(), path, cache_path, last_modified)

        CompilationManager.files_to_compile.task_done()
    except Exception as e:
        log_fail("Internal Compiler Error: ")
        log_fail(traceback.format_exc())
        exceptions = True
        CompilationManager.finish_file(path)
        CompilationManager.files_to_compile.task_done()
