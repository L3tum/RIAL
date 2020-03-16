import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import List

import lark
from colorama import init
from timeit import default_timer as timer

from rial.LLVMTransformer import LLVMTransformer
from rial.codegen import CodeGen
from rial.linking import Linker
from rial.log import log_fail


def main(options):
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

    path = source_path.joinpath("main.rial")

    if not path.exists():
        log_fail("Main file not found in source path!")
        sys.exit(1)

    with open(f"{self_dir}/concept/grammar.lark", "r") as grammar:
        gram = grammar.read()

    transformer = LLVMTransformer()
    parser = lark.Lark(gram, start='program', parser="lalr", transformer=transformer)
    codegen = CodeGen(options.opt_level)
    object_files: List[str] = list()

    while path is not None:
        with open(path, "r") as src:
            module = codegen.get_module(_mod_name_from_path(str(path).replace(str(source_path), "")))
            transformer.init(module)
            ast = parser.parse(src.read())

            if options.print_tokens:
                print(ast.pretty())

            mod = codegen.compile_ir(module)

            ir_file = Path(str(path).replace(str(source_path), str(cache_path)).replace(".rial", ".ll"))
            object_file = Path(str(path).replace(str(source_path), str(cache_path)).replace(".rial", ".o"))
            asm_file = Path(str(path).replace(str(source_path), str(cache_path)).replace(".rial", ".asm"))

            if options.print_ir:
                codegen.save_ir(ir_file, module)

            if options.print_asm:
                codegen.save_assembly(asm_file, mod)

            codegen.save_object(object_file, mod)
            object_files.append(str(object_file))

            path = None

    Linker(bin_path, project_name, options.print_link_command).link_files(object_files)


def _mod_name_from_path(path: str) -> str:
    string = path.strip('/').replace('.rial', '').replace('/', ':')
    return string


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
    parser.add_argument('--print-link-command', action='store_true', default=False,
                        help="Prints the command used for linking the object files")

    return parser.parse_args()


if __name__ == "__main__":
    init()
    opts = parse_arguments()
    main(opts)
