from abc import ABCMeta, abstractmethod
from typing import List


class IPlatform:
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_source_file_extension(self) -> str:
        return ".rial"

    @abstractmethod
    def get_object_file_extension(self) -> str:
        return ".o"

    @abstractmethod
    def get_asm_file_extension(self) -> str:
        return ".asm"

    @abstractmethod
    def get_ir_file_extension(self) -> str:
        return ".ll"

    @abstractmethod
    def get_bc_file_extension(self) -> str:
        return ".bc"

    @abstractmethod
    def get_exe_file_extension(self) -> str: raise NotImplementedError

    @abstractmethod
    def get_link_command(self, object_files: List[str], exe_file: str): raise NotImplementedError

    @abstractmethod
    def get_opt_command(self, ir_file: str): raise NotImplementedError
