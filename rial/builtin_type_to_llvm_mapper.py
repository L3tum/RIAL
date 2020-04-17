import re
from typing import Optional

from llvmlite import ir
from llvmlite.ir import Type

NULL = ir.Constant(ir.IntType(8), 0).inttoptr(ir.PointerType(ir.IntType(8)))
TRUE = ir.Constant(ir.IntType(1), 1)
FALSE = ir.Constant(ir.IntType(1), 0)


def map_shortcut_to_type(shortcut: str) -> str:
    if shortcut == "int":
        return "Int32"

    if shortcut == "long":
        return "Int64"

    if shortcut == "double":
        return "Double64"

    if shortcut == "float":
        return "Float32"

    if shortcut == "bool":
        return "Boolean"

    return shortcut


def map_type_to_llvm(rial_type: str) -> Optional[Type]:
    if rial_type == "Int32":
        # 32bit integer
        return ir.IntType(32)

    if rial_type == "Int64":
        return ir.IntType(64)

    if rial_type == "Boolean":
        # 1 bit
        return ir.IntType(1)

    if rial_type == "CString":
        # Char pointer
        return ir.IntType(8).as_pointer()

    if rial_type == "void":
        # Void
        return ir.VoidType()

    if rial_type == "Float32":
        return ir.FloatType()

    if rial_type == "Double64":
        return ir.DoubleType()

    # Variable integer
    match = re.match(r"^Int([0-9]+)$", rial_type)

    if match is not None:
        count = match.group(1)

        return ir.IntType(int(count))

    return None
