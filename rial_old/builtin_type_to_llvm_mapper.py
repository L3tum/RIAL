import re
from typing import Optional

from llvmlite import ir
from llvmlite.ir import Type, BaseStructType, Constant

from rial.LLVMUIntType import LLVMUIntType
from rial.compilation_manager import CompilationManager
from rial.metadata.RIALIdentifiedStructType import RIALIdentifiedStructType

NULL = ir.Constant(ir.IntType(8), 0).inttoptr(ir.PointerType(ir.IntType(8)))
TRUE = ir.Constant(ir.IntType(1), 1)
FALSE = ir.Constant(ir.IntType(1), 0)
Int32 = ir.IntType(32)
Long = ir.IntType(64)


def get_size(ty: Type) -> Optional[int]:
    if isinstance(ty, ir.IntType):
        return int(ty.width / 8)
    if isinstance(ty, ir.FloatType):
        return int(32 / 8)
    if isinstance(ty, ir.DoubleType):
        return int(64 / 8)
    if isinstance(ty, BaseStructType):
        return ty.get_abi_size(CompilationManager.codegen.target_machine.target_data)
    return None


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
    match = re.match(r"^Int([0-9]+)$", rial_type)

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

    if isinstance(llvm_type, RIALIdentifiedStructType):
        return llvm_type.name

    if isinstance(llvm_type, ir.ArrayType):
        return f"{map_llvm_to_type(llvm_type.element)}[]"

    if isinstance(llvm_type, ir.FunctionType):
        return str(llvm_type)

    return llvm_type


def convert_number_to_constant(value: str) -> Constant:
    value.replace("_", "")
    value_lowered = value.lower()

    if "." in value or "e" in value:
        if value.endswith("f"):
            return ir.FloatType()(float(value.strip("f")))
        if value.endswith("h"):
            return ir.HalfType()(float(value.strip("h")))
        return ir.DoubleType()(float(value.strip("d")))

    if value.startswith("0x"):
        return Int32(int(value, 16))

    if value.startswith("0b"):
        return Int32(int(value, 2))

    if value_lowered.endswith("b"):
        return LLVMUIntType(8)(int(value_lowered.strip("b")))

    if value_lowered.endswith("ul"):
        return LLVMUIntType(64)(int(value_lowered.strip("ul")))

    if value_lowered.endswith("u"):
        return LLVMUIntType(32)(int(value_lowered.strip("u")))

    if value_lowered.endswith("l"):
        return ir.IntType(64)(int(value_lowered.strip("l")))

    return Int32(int(value))
