import platform
from typing import List, Dict

from rial.linking.linking_options import LinkingOptions
from rial.platform.IPlatform import IPlatform
from rial.platform.LinuxPlatform import LinuxPlatform

platforms: Dict[str, IPlatform] = {
    "Linux": LinuxPlatform()
}


class Platform:
    @staticmethod
    def get_source_file_extension() -> str:
        return Platform.get_platform().get_source_file_extension()

    @staticmethod
    def get_object_file_extension() -> str:
        return Platform.get_platform().get_object_file_extension()

    @staticmethod
    def get_asm_file_extension() -> str:
        return Platform.get_platform().get_asm_file_extension()

    @staticmethod
    def get_ir_file_extension() -> str:
        return Platform.get_platform().get_ir_file_extension()

    @staticmethod
    def get_bc_file_extension() -> str:
        return Platform.get_platform().get_bc_file_extension()

    @staticmethod
    def get_exe_file_extension() -> str:
        return Platform.get_platform().get_exe_file_extension()

    @staticmethod
    def get_link_options() -> LinkingOptions:
        return Platform.get_platform().get_link_options()

    @staticmethod
    def get_platform() -> IPlatform:
        system = platform.system()

        if system in platforms:
            return platforms[system]

        raise NotImplementedError
