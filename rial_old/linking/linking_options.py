from typing import List


class LinkingOptions:
    llvm_linker_executable: str
    linker_executable: str
    linker_pre_args: List[str] = list()
    linker_object_args: List[str] = list()
    linker_post_args: List[str] = list()
    linker_output_arg: str
