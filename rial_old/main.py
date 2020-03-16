import argparse
import datetime
import os
import shutil
import sys
import ctypes
from ctypes import CFUNCTYPE
from pathlib import Path
from typing import List

from colorama import init
from rply import Token

from rial_old.ast.program import Program
from rial_old.codegen import CodeGen
from rial_old.lexer import Lexer
from rial_old.log import log_fail, log_success

from timeit import default_timer as timer

from rial_old.parser import Parser, ParserState


def main(options):
    abs_start = timer()
    lexer = Lexer().get_lexer()
    parser = Parser().get_parser()
    codegen = CodeGen(options.opt_level)

    abs_cwd = os.path.abspath(options.workdir)

    source_path = Path(os.path.join(abs_cwd, "src"))
    cache_path = Path(os.path.join(abs_cwd, "cache"))

    if cache_path.exists():
        shutil.rmtree(cache_path)

    cache_path.mkdir(parents=False, exist_ok=False)

    if not source_path.exists():
        log_fail("Source path does not exist!")
        sys.exit(1)

    path = source_path.joinpath("main.rial_old")

    if not path.exists():
        log_fail("Main file not found in source path!")
        sys.exit(1)

    while True:
        with open(path, "r") as src:
            filename = str(path).replace(abs_cwd + "/src/", "").replace(".rial_old", "")
            name = filename.replace("/", ":")
            text = src.read()
            tokens = lexer.lex(text)

            module = codegen.get_module(name=name)
            state = ParserState(name, module)
            program: Program = parser.parse(tokens, state=state)
            program.eval()
            mod = codegen.compile_ir(state.module)

            if options.print_ir:
                codegen.save_ir(os.path.join(cache_path, filename + ".ll"), state.module)
            if options.print_asm:
                codegen.save_assembly(os.path.join(cache_path, filename + ".asm"), mod)

            codegen.save_object(os.path.join(cache_path, filename + ".o"), mod)

            break

    end = timer()

    # Look up the function pointer (a Python int)
    # func_ptr = codegen.engine.get_function_address("main")
    #
    # # Run the function via ctypes
    # cfunc = CFUNCTYPE(ctypes.c_void_p)(func_ptr)
    # cfunc()

    log_success(f"Compiled in {str(datetime.timedelta(seconds=(end - abs_start)))}")


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-w', '--workdir', help="Overwrite working directory", type=str, default=os.getcwd())
    parser.add_argument('--print-tokens', help="Prints the list of tokens to stdout", action="store_true",
                        default=False)
    parser.add_argument('--print-ir', help="Prints the LLVM IR", action="store_true",
                        default=False)
    parser.add_argument('--print-asm', help="Prints the native assembly", action="store_true",
                        default=False)
    parser.add_argument('--opt-level', type=int, default=0, help="Optimization level to use", choices=(0, 1, 2, 3))

    return parser.parse_args()


if __name__ == "__main__":
    init()
    opts = parse_arguments()
    main(opts)
