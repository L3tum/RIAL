from typing import Optional

from llvmlite.ir import Type, IntType, DoubleType, FloatType, HalfType
from llvmlite.ir.types import _BaseFloatType

from rial.ir.LLVMUIntType import LLVMUIntType


def get_casting_function(src_type: Type, target_type: Type) -> Optional[str]:
    if isinstance(src_type, LLVMUIntType):
        if isinstance(target_type, LLVMUIntType):
            if src_type.width > target_type.width:
                return 'trunc'
            else:
                return 'zext'
        elif isinstance(target_type, IntType):
            if src_type.width > target_type.width:
                return 'trunc'
            else:
                return 'zext'
        elif isinstance(target_type, _BaseFloatType):
            return 'uitofp'
    elif isinstance(src_type, IntType):
        if isinstance(target_type, LLVMUIntType):
            if src_type.width > target_type.width:
                return 'trunc'
            else:
                return 'zext'
        elif isinstance(target_type, IntType):
            if src_type.width > target_type.width:
                return 'trunc'
            else:
                return 'sext'
        elif isinstance(target_type, _BaseFloatType):
            return 'sitofp'
    elif isinstance(src_type, FloatType):
        if isinstance(target_type, LLVMUIntType):
            return 'fptoui'
        elif isinstance(target_type, IntType):
            return 'fptosi'
        elif isinstance(target_type, DoubleType):
            return 'fpext'
        elif isinstance(target_type, HalfType):
            return 'fptrunc'
    elif isinstance(src_type, DoubleType):
        if isinstance(target_type, LLVMUIntType):
            return 'fptoui'
        elif isinstance(target_type, IntType):
            return 'fptosi'
        elif isinstance(target_type, FloatType) or isinstance(target_type, HalfType):
            return 'fptrunc'
    elif isinstance(src_type, HalfType):
        if isinstance(target_type, LLVMUIntType):
            return 'fptoui'
        elif isinstance(target_type, IntType):
            return 'fptosi'
        elif isinstance(target_type, FloatType) or isinstance(target_type, DoubleType):
            return 'fpext'

    return None
