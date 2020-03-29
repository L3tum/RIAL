from typing import List
import subprocess

from shutil import which
import shlex

from rial.platform.Platform import Platform


class Linker:
    @staticmethod
    def link_files(object_files: List[str], exe_file: str, print_link_command: bool, strip: bool):
        args = Platform.get_link_command(object_files, exe_file)

        if print_link_command:
            print(args)

        subprocess.run(shlex.split(args))

        if strip:
            strip_path = which('llvm-strip')

            if strip_path is None:
                strip_path = which('llvm-strip-7')

            if strip_path is not None:
                args = f"{strip_path} --strip-all {exe_file}"
                subprocess.run(shlex.split(args))
