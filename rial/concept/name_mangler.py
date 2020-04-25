from typing import List, Type

from rial.LLVMUIntType import LLVMUIntType


def mangle_function_name(full_function_name: str, args: List[Type], struct_name: str = None):
    return f"{struct_name is not None and f'{struct_name}.' or ''}{full_function_name}.{'.'.join([isinstance(arg, LLVMUIntType) and arg.rial_repr() or str(arg) for arg in args])}" \
        .replace("%", "").replace("\"", "").replace("*", "")
