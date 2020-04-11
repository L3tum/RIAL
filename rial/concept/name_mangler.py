from typing import List


def mangle_function_name(full_function_name: str, args: List[str]):
    return f"{full_function_name}.{'.'.join(args)}".replace("%", "").replace("\"", "")
