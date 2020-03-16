import os
import pathlib
from typing import List, Optional
import subprocess

from rial.log import log_fail
from shutil import which
import shlex


class Linker:
    path: str
    name: str
    print_link_command: bool

    def __init__(self, bin_path: str, project_name: str, print_link_command: bool):
        self.path = bin_path
        self.name = project_name
        self.print_link_command = print_link_command

    @staticmethod
    def _check_linker_exists() -> Optional[str]:
        return which("cc")

    def link_files(self, files: List[str]):
        out_file = os.path.join(self.path, self.name)
        linker_path = self._check_linker_exists()

        if linker_path is not None:
            args = f"{linker_path} {' '.join(files)} -o {out_file}"

            if self.print_link_command:
                print(args)

            subprocess.run(shlex.split(args))
        else:
            log_fail(f"Could not find Linker {'cc'} in PATH")
