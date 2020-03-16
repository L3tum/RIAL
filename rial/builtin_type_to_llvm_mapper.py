import re
from typing import Optional

from llvmlite import ir
from llvmlite.ir import Type


def map_type_to_llvm(rial_type: str) -> Optional[Type]:
    if rial_type == "int":
        # 32bit integer
        return ir.IntType(32)

    if rial_type == "bool":
        # 1 bit
        return ir.IntType(1)

    if rial_type == "CString":
        # Char pointer
        return ir.IntType(8).as_pointer()

    if rial_type == "void":
        # Void
        return ir.VoidType()

    # Variable integer
    match = re.match(r"^i([0-9]+)$", rial_type)

    if match is not None:
        count = match.group(1)

        return ir.IntType(int(count))

    return None
