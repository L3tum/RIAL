import re
from typing import Optional

from llvmlite import ir
from llvmlite.ir import Type

from rial.LLVMUIntType import LLVMUIntType

NULL = ir.Constant(ir.IntType(8), 0).inttoptr(ir.PointerType(ir.IntType(8)))
TRUE = ir.Constant(ir.IntType(1), 1)
FALSE = ir.Constant(ir.IntType(1), 0)


def null(ty):
    return ir.Constant(ty, None)


def is_builtin_type(ty: str):
    return ty in ("Int32", "Int64", "UInt64", "UInt64", "Double64", "Float32", "Boolean", "Byte", "Char", "Half")


def map_shortcut_to_type(shortcut: str) -> str:
    if shortcut == "int":
        return "Int32"

    if shortcut == "long":
        return "Int64"

    if shortcut == "ulong":
        return "UInt64"

    if shortcut == "uint":
        return "UInt32"

    if shortcut == "double":
        return "Double64"

    if shortcut == "float":
        return "Float32"

    if shortcut == "bool":
        return "Boolean"

    if shortcut == "byte":
        return "Byte"

    if shortcut == "char":
        return "Char"

    if shortcut == "half":
        return "Half"

    return shortcut


def map_type_to_llvm(rial_type: str) -> Optional[Type]:
    rial_type = map_shortcut_to_type(rial_type)

    if rial_type == "Int32":
        # 32bit integer
        return ir.IntType(32)

    if rial_type == "UInt32":
        return LLVMUIntType(32)

    if rial_type == "Int64":
        return ir.IntType(64)

    if rial_type == "UInt64":
        return LLVMUIntType(64)

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

    if rial_type == "Byte":
        return LLVMUIntType(8)

    if rial_type == "Char":
        return ir.IntType(8)

    if rial_type == "Half":
        return ir.HalfType()

    # Variable integer
    match = re.match(r"^i([0-9]+)$", rial_type)

    if match is not None:
        count = match.group(1)

        return ir.IntType(int(count))

    return None


def map_llvm_to_type(llvm_type: Type):
    # TODO: Handle more types
    # TODO: Handle structs
    # TODO: Handle strings
    if isinstance(llvm_type, LLVMUIntType):
        return f"UInt{llvm_type.width}"

    if isinstance(llvm_type, ir.IntType):
        return f"Int{llvm_type.width}"

    if isinstance(llvm_type, ir.FloatType):
        return "Float32"

    if isinstance(llvm_type, ir.DoubleType):
        return "Double64"

    if isinstance(llvm_type, ir.VoidType):
        return "void"

    if isinstance(llvm_type, ir.PointerType):
        if isinstance(llvm_type.pointee, ir.IntType):
            if llvm_type.pointee.width == 8:
                return "CString"

    return llvm_type
