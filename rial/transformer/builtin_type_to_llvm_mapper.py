import re
from functools import lru_cache
from typing import Optional

from llvmlite import ir
from llvmlite.ir import Type, Constant, IdentifiedStructType

from rial.ir.LLVMUIntType import LLVMUIntType

NULL = ir.Constant(ir.IntType(8), 0).inttoptr(ir.PointerType(ir.IntType(8)))
TRUE = ir.Constant(ir.IntType(1), 1)
FALSE = ir.Constant(ir.IntType(1), 0)
Int32 = ir.IntType(32)
Long = ir.IntType(64)

SHORTCUT_TO_TYPE = {
    'int': 'Int32',
    'long': 'Int64',
    'uint': 'UInt32',
    'ulong': 'UInt64',
    'double': 'Double64',
    'float': 'Float32',
    'bool': 'Boolean',
    'byte': 'Byte',
    'sbyte': 'SByte',
    'char': 'Char',
    'half': 'Half',
    'void': 'Void',
    'CString': 'Char[]'
}

TYPE_TO_LLVM = {
    'Int32': ir.IntType(32),
    'UInt32': LLVMUIntType(32),
    'Int64': ir.IntType(64),
    'UInt64': LLVMUIntType(64),
    'Boolean': ir.IntType(1),
    'Void': ir.VoidType(),
    'Float32': ir.FloatType(),
    'Double64': ir.DoubleType(),
    'Byte': LLVMUIntType(8),
    'SByte': ir.IntType(8),
    'Char': LLVMUIntType(8),
    'Half': ir.HalfType()
}


def null(ty):
    return ir.Constant(ty, None)


@lru_cache(len(TYPE_TO_LLVM) + 20)
def is_builtin_type(ty: str):
    return map_type_to_llvm(ty) is not None


@lru_cache(len(SHORTCUT_TO_TYPE) + 20)
def map_shortcut_to_type(shortcut: str) -> str:
    return SHORTCUT_TO_TYPE[shortcut] if shortcut in SHORTCUT_TO_TYPE else shortcut


@lru_cache(128)
def map_type_to_llvm(rial_type: str) -> Optional[Type]:
    rial_type = map_shortcut_to_type(rial_type)

    if rial_type in TYPE_TO_LLVM:
        return TYPE_TO_LLVM[rial_type]

    if rial_type == "CString":
        # Char pointer
        return ir.IntType(8).as_pointer()

    # Variable integer
    match = re.match(r"^Int([0-9]+)$", rial_type)

    if match is not None:
        count = match.group(1)

        return ir.IntType(int(count))

    # Variable uinteger
    match = re.match(r"^UInt([0-9]+)$", rial_type)

    if match is not None:
        count = match.group(1)

        return LLVMUIntType(int(count))

    return None


@lru_cache(128, typed=True)
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

    if isinstance(llvm_type, IdentifiedStructType):
        return llvm_type.name

    if isinstance(llvm_type, ir.ArrayType):
        return f"{map_llvm_to_type(llvm_type.element)}[]"

    if isinstance(llvm_type, ir.FunctionType):
        return str(llvm_type)

    return llvm_type


@lru_cache(128)
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
