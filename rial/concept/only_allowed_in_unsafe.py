from contextlib import contextmanager

from rial.LLVMGen import LLVMGen


@contextmanager
def only_allowed_in_unsafe(llvmgen: LLVMGen):
    if not llvmgen.currently_unsafe:
        raise PermissionError()
