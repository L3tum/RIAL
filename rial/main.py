import argparse
import multiprocessing
import os
import shutil
import sys
import threading
import traceback
from pathlib import Path
from timeit import default_timer as timer
from typing import List, Dict

from colorama import init
from llvmlite.binding import ModuleRef

from rial.ASTVisitor import ASTVisitor
from rial.PrimitiveASTTransformer import PrimitiveASTTransformer
from rial.codegen import CodeGen
from rial.compilation_manager import CompilationManager
from rial.configuration import Configuration
from rial.linking.linker import Linker
from rial.log import log_fail
from rial.concept.parser import Lark_StandAlone
from rial.profiling import execution_events, ExecutionStep, set_profiling, run_with_profiling, display_top
from rial.platform.Platform import Platform
import tracemalloc


def main(opts):
    path = source_path.joinpath("main.rial")

    if not path.exists():
        log_fail("Main file not found in source path!")
        sys.exit(1)

    threads = list()

    compilation_manager.files_to_compile.put(path)

    for i in range(multiprocessing.cpu_count()):
        t = threading.Thread(target=compile_file, args=(opts,))
        t.daemon = True
        t.start()
        threads.append(t)

    compilation_manager.files_to_compile.join()

    modules: Dict[str, ModuleRef] = dict()

    if opts.release:
        with run_with_profiling("main", ExecutionStep.COMPILE_MOD):
            # Since the main module is dependent on all other modules, it will be the last to add
            # If it's not the actual main module then that's no big deal either
            main_module = compilation_manager.modules[list(compilation_manager.modules.keys())[-1]]

            for key in list(compilation_manager.modules.keys()):
                mod = compilation_manager.modules[key]

                # Skip last
                if main_module == mod:
                    continue

                main_module.link_in(mod, False)

            # "Virtual" main
            modules[str(source_path) + "/main.rial"] = main_module
    else:
        modules = compilation_manager.modules

    object_files: List[str] = list()

    for path in list(modules.keys()):
        mod = modules[path]
        codegen.generate_final_module(mod)

        if opts.print_ir:
            ir_file = Path(str(path).replace(str(source_path), str(cache_path)).replace(".rial", ".ll"))
            codegen.save_ir(ir_file, mod)

        if opts.print_asm:
            asm_file = Path(str(path).replace(str(source_path), str(cache_path)).replace(".rial", ".asm"))
            codegen.save_assembly(asm_file, mod)

        if opts.print_lbc:
            llvm_bitcode_file = Path(str(path).replace(str(source_path), str(cache_path)).replace(".rial", ".lbc"))
            codegen.save_llvm_bitcode(llvm_bitcode_file, mod)

        object_file = Path(str(path).replace(str(source_path), str(cache_path)).replace(".rial", ".o"))
        codegen.save_object(object_file, mod)
        object_files.append(str(object_file))

    with run_with_profiling(project_name, ExecutionStep.LINK_EXE):
        exe_path = os.path.join(bin_path, f"{project_name}{Platform.get_exe_file_extension()}")
        Linker.link_files(object_files, exe_path, opts.print_link_command, opts.strip)


def compile_file(opts):
    try:
        primitive_transformer = PrimitiveASTTransformer()

        while True:
            path = compilation_manager.files_to_compile.get()

            if not Path(path).exists():
                log_fail(f"Could not find {path}")
                compilation_manager.finish_file(path)
                compilation_manager.files_to_compile.task_done()
                continue

            file = str(path).replace(str(source_path), "")
            module_name = file.strip('/').replace('.rial', '').replace('/', ':')
            module_name = project_name + ":" + module_name
            module = codegen.get_module(module_name)
            transformer = ASTVisitor(compilation_manager.ps, module, file.split('/')[-1], str(source_path))
            primitive_transformer.init(transformer.llvmgen)
            parser = Lark_StandAlone(transformer=primitive_transformer)

            with run_with_profiling(file, ExecutionStep.READ_FILE):
                with open(path, "r") as src:
                    contents = src.read()

            with run_with_profiling(file, ExecutionStep.PARSE_FILE):
                ast = parser.parse(contents)

            if opts.print_tokens:
                print(ast.pretty())

            transformer.visit(ast)

            mod = codegen.compile_ir(module)
            compilation_manager.modules[path] = mod

            compilation_manager.finish_file(path)
            compilation_manager.files_to_compile.task_done()
    except Exception as e:
        log_fail("Internal Compiler Error: ")
        log_fail(traceback.format_exc())
        os._exit(-1)
    finally:
        del parser


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-w', '--workdir', help="Overwrite working directory", type=str, default=os.getcwd())
    parser.add_argument('--print-tokens', help="Prints the list of tokens to stdout", action="store_true",
                        default=False)
    parser.add_argument('--print-ir', help="Prints the LLVM IR", action="store_true",
                        default=False)
    parser.add_argument('--print-asm', help="Prints the native assembly", action="store_true",
                        default=False)
    parser.add_argument('--print-lbc', help="Prints the LLVM bitcode", action="store_true",
                        default=False)
    parser.add_argument('--opt-level', type=str, default="0", help="Optimization level to use",
                        choices=("0", "1", "2", "3", "s", "z"))
    parser.add_argument('--print-link-command', action='store_true', default=False,
                        help="Prints the command used for linking the object files")
    parser.add_argument('--release', action='store_true', default=False, help="Release mode")
    parser.add_argument('--profile', action='store_true', default=False, help="Profile own execution steps")
    parser.add_argument('--profile-mem', action='store_true', default=False, help="Profile memory allocations")
    parser.add_argument('--strip', action='store_true', default=False,
                        help="Strips debug information from the resulting exe")

    return parser.parse_args()


if __name__ == "__main__":
    start = timer()
    init()
    options = parse_arguments()

    if options.profile_mem:
        tracemalloc.start()
        start_snapshot = tracemalloc.take_snapshot()

    set_profiling(options.profile)

    self_dir = "/".join(f"{__file__}".split('/')[0:-1])
    project_path = str(os.path.abspath(options.workdir))
    project_name = project_path.split('/')[-1]

    source_path = Path(os.path.join(project_path, "src"))
    cache_path = Path(os.path.join(project_path, "cache"))
    bin_path = Path(os.path.join(project_path, "bin"))

    if cache_path.exists():
        shutil.rmtree(cache_path)

    cache_path.mkdir(parents=False, exist_ok=False)

    if bin_path.exists():
        shutil.rmtree(bin_path)

    bin_path.mkdir(parents=False, exist_ok=False)

    if not source_path.exists():
        log_fail("Source path does not exist!")
        sys.exit(1)

    config = Configuration(project_name, source_path, cache_path, bin_path, options)
    compilation_manager = CompilationManager.init(config)
    codegen = CodeGen(options.opt_level)

    main(options)

    end = timer()

    if options.profile:
        print("----- PROFILING -----")
        total = 0
        for event in execution_events:
            print(event)
            total += event.time_taken_seconds
        print(f"TOTAL : {(end - start).__round__(3)}s")
        print("")

    if options.profile_mem:
        end_snapshot = tracemalloc.take_snapshot()
        display_top(end_snapshot)
