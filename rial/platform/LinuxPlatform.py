from typing import List

from rial.platform.IPlatform import IPlatform


class LinuxPlatform(IPlatform):
    def get_source_file_extension(self) -> str:
        return super().get_source_file_extension()

    def get_object_file_extension(self) -> str:
        return super().get_object_file_extension()

    def get_asm_file_extension(self) -> str:
        return super().get_asm_file_extension()

    def get_ir_file_extension(self) -> str:
        return super().get_ir_file_extension()

    def get_bc_file_extension(self) -> str:
        return super().get_bc_file_extension()

    def get_exe_file_extension(self) -> str:
        return ""

    def get_link_command(self, object_files: List[str], exe_file: str):
        return f"cc {' '.join(object_files)} -o {exe_file}"

    def get_opt_command(self, ir_file: str):
        return f"opt {ir_file} -o {ir_file.replace(self.get_ir_file_extension(), self.get_bc_file_extension())}"
