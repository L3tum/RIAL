from typing import List


def mangle_function_name(full_function_name: str, rial_arg_types: List[str], struct_name: str = None):
    return f"{struct_name is not None and f'{struct_name}.' or ''}{full_function_name}.{'.'.join(rial_arg_types)}" \
        .replace("%", "").replace("\"", "").replace("*", "")


def mangle_global_name(module_name: str, global_name: str) -> str:
    return f"{module_name}:{global_name}"
