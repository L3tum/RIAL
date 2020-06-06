import argparse
import json
import multiprocessing
import os
import shutil
from pathlib import Path
from timeit import default_timer as timer

import anyconfig
from colorama import init
from munch import munchify

from rial.compilation_manager import CompilationManager
from rial.configuration import Configuration
from rial.profiling import set_profiling, execution_events, display_top
from rial.util.util import pythonify, monkey_patch, rreplace

DEFAULT_OPTIONS = {
    'config': {
        'print_tokens': False,
        'print_asm': False,
        'print_ir': False,
        'disable_cache': False,
        'disable_opt': False,
        'use_object_files': True,
        'opt_level': '1',
        'print_link_command': False,
        'release': False,
        'profile': False,
        'profile_mem': False,
        'profile_gil': False,
        'strip': False,
        'file': None,
        'compile_units': multiprocessing.cpu_count(),
    },
    'release': {
        'opt_level': '3',
        'release': True,
        'strip': True,
    }
}


def main(options):
    start = timer()

    # Monkey patch functions in
    monkey_patch()

    init()

    if options.profile_mem:
        import tracemalloc
        tracemalloc.start()
        start_snapshot = tracemalloc.take_snapshot()

    set_profiling(options.profile)

    self_dir = Path(rreplace(__file__.replace("main.py", ""), "/rial", "", 1)).joinpath("std")
    project_path = str(os.path.abspath(options.workdir))
    project_name = project_path.split('/')[-1]

    source_path = Path(os.path.join(project_path, "src"))
    cache_path = Path(os.path.join(project_path, "cache"))
    output_path = Path(os.path.join(project_path, "output"))
    bin_path = Path(os.path.join(project_path, "bin"))

    cache_path.mkdir(parents=False, exist_ok=True)

    if output_path.exists():
        shutil.rmtree(output_path)

    output_path.mkdir(parents=False, exist_ok=False)

    if bin_path.exists():
        shutil.rmtree(bin_path)

    bin_path.mkdir(parents=False, exist_ok=False)

    if not source_path.exists():
        raise FileNotFoundError(str(source_path))

    config = Configuration(project_name, source_path, cache_path, output_path, bin_path, self_dir, options)
    CompilationManager.init(config)
    CompilationManager.compiler()
    CompilationManager.fini()

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
        import tracemalloc
        end_snapshot = tracemalloc.take_snapshot()
        display_top(end_snapshot)


def parse_prelim_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('-w', '--workdir', help="Overwrite working directory", type=str, default="")
    parser.add_argument('-f', '--file', help="Overwrite start file", type=str, default=None)
    parser.add_argument('--print-tokens', help="Prints the list of tokens to stdout", action="store_true", default=None)
    parser.add_argument('--print-asm', help="Prints the native assembly", action="store_true", default=None)
    parser.add_argument('--print-ir', help="Prints the LLVM IR", action="store_true", default=None)
    parser.add_argument('--opt-level', type=str, help="Optimization level to use",
                        choices=("0", "1", "2", "3", "s", "z"), default=None)
    parser.add_argument('--print-link-command', action='store_true',
                        help="Prints the command used for linking the object files", default=None)
    parser.add_argument('--release', action='store_true', help="Release mode", default=None)
    parser.add_argument('--use-object-files', action='store_true',
                        help="Use object files rather than LLVM bitcode files for linking", default=None)
    parser.add_argument('--disable-cache', action='store_true',
                        help="Disable cache", default=None)
    parser.add_argument('--disable-opt', action='store_true',
                        help="Completely disables any kind of optimization", default=None)
    parser.add_argument('--profile', help="Profiles the compiler", action="store_true", default=None)
    parser.add_argument('--profile-gil', help="Profiles the GIL", action="store_true", default=None)
    parser.add_argument('--print-options', help="Prints the passed options", action="store_true", default=False)

    return parser.parse_known_args()


def parse_config_file_arguments(workdir: str):
    workdir = Path(workdir)
    return anyconfig.load([
        str(workdir.joinpath("rial.json")),
        str(workdir.joinpath("rial.yaml")),
        str(workdir.joinpath("rial.toml")),
        str(workdir.joinpath("rial.ini")),
        str(workdir.joinpath("rial.xml")),
        str(workdir.joinpath("rial.properties")),
    ], ac_ignore_missing=True)


def start():
    opts = DEFAULT_OPTIONS

    # Remove default (None) values
    ops = {k: v for k, v in vars(parse_prelim_arguments()[0]).items() if v is not None}

    # Check if workdir is set, otherwise assume cwd
    if ops['workdir'] == "":
        ops['workdir'] = os.getcwd()
    else:
        ops['workdir'] = os.path.abspath(ops['workdir'])

    # Merge base config and file config (giving priority to file config)
    anyconfig.merge(opts, parse_config_file_arguments(ops['workdir']), ac_merge=anyconfig.MS_DICTS_AND_LISTS,
                    ac_parse_value=True)

    # Merge release into config to overwrite for release mode
    if ('release' in ops and ops['release']) or (
            'config' in opts and 'release' in opts['config'] and opts['config']['release']):
        anyconfig.merge(opts['config'], opts['release'], ac_merge=anyconfig.MS_DICTS_AND_LISTS)

    # Merge CLI args
    anyconfig.merge(opts, {'config': ops}, ac_merge=anyconfig.MS_DICTS_AND_LISTS)

    opts = opts['config']

    opts = pythonify(opts)

    # Validate the config
    schema = anyconfig.load(__file__.replace("main.py", "") + "/concept/config_schema.json")
    anyconfig.validate(opts, schema, ac_schema_safe=False)

    # schema = anyconfig.gen_schema(opts, ac_schema_type="strict")
    # schema_s = anyconfig.dumps(schema, "json")
    #
    # with open(__file__.replace("main.py", "") + "/concept/config_schema.json", "w") as file:
    #     file.write(schema_s)

    if opts['print_options']:
        print(json.dumps(opts, sort_keys=True, indent=4))

    opts = munchify(opts)

    main(opts)


if __name__ == "__main__":
    start()
