import re
from functools import lru_cache

from llvmlite import ir
from llvmlite.ir import Value, GlobalValue

from rial.rial_types.RIALAccessModifier import RIALAccessModifier


# TODO: Use to implement variables and not just struct and global variables
class RIALVariable:
    name: str
    rial_type: str
    access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE
    backing_value: Value
    global_variable: bool

    def __init__(self, name: str, rial_type: str, backing_value: Value,
                 access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE):
        from rial.builtin_type_to_llvm_mapper import map_shortcut_to_type

        if not isinstance(rial_type, str):
            raise TypeError(rial_type)

        self.name = name
        self.rial_type = map_shortcut_to_type(rial_type)
        self.access_modifier = access_modifier
        self.backing_value = backing_value
        self.global_variable = isinstance(self.backing_value, GlobalValue)

    def __str__(self):
        return f"{self.name}: {self.rial_type} = {self.backing_value}: {self.llvm_type}"

    @property
    def raw_backing_value(self):
        from rial.ParserState import ParserState
        return (self._is_loaded or (self.rial_type == "CString" and self.backing_value.type == ir.IntType(
            8).as_pointer())) and self.backing_value or ParserState.llvmgen().builder.load(
            self.backing_value)

    @property
    @lru_cache(1)
    def raw_llvm_type(self):
        from rial.ParserState import ParserState
        return ParserState.map_type_to_llvm_no_pointer(self.rial_type)

    @property
    @lru_cache(1)
    def llvm_type(self):
        from rial.ParserState import ParserState

        if isinstance(self.backing_value, ir.CallInstr):
            return self.backing_value.type

        return ParserState.map_type_to_llvm(self.rial_type)

    @property
    @lru_cache(1)
    def _is_loaded(self):
        return not isinstance(self.backing_value.type, ir.PointerType) and self.backing_value.type == self.raw_llvm_type

    @property
    @lru_cache(1)
    def is_pointer(self):
        if isinstance(self.backing_value, ir.FormattedConstant):
            return True
        if isinstance(self.backing_value, ir.Constant):
            return False
        if isinstance(self.backing_value, ir.AllocaInstr):
            return True
        if isinstance(self.backing_value, ir.GEPInstr):
            return True
        if isinstance(self.backing_value, ir.Argument):
            if isinstance(self.backing_value.type, ir.PointerType):
                return True
            return False
        if isinstance(self.backing_value, ir.CastInstr):
            if isinstance(self.backing_value.type, ir.PointerType):
                return True
            return False

        return False

    @property
    def is_primitive(self):
        from rial.builtin_type_to_llvm_mapper import is_builtin_type
        return is_builtin_type(self.rial_type)

    @property
    def is_array(self):
        return self.rial_type.endswith("]")

    @property
    def array_type(self):
        return re.sub(r"\[[0-9]+\]$", "", self.rial_type)

    @property
    def is_constant_sized_array(self):
        return self.is_array and isinstance(self.raw_llvm_type, ir.ArrayType) and isinstance(self.raw_llvm_type.count,
                                                                                             int)
