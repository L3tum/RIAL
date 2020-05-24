from functools import lru_cache
from typing import Tuple, Optional

from llvmlite import ir
from llvmlite.ir import Value, GlobalValue, AllocaInstr, Argument, PointerType, GEPInstr, CastInstr, CallInstr

from rial.builtin_type_to_llvm_mapper import is_builtin_type, is_array
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


# TODO: Use to implement variables and not just struct and global variables
class RIALVariable:
    name: str
    rial_type: str
    access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE
    backing_value: Value
    global_variable: bool
    sloc: Tuple[int, int]

    def __init__(self, name: str, rial_type: str, backing_value: Optional[Value] = None,
                 access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE, sloc: Tuple[int, int] = None):

        if not isinstance(rial_type, str):
            raise TypeError(rial_type)
        if isinstance(backing_value, str):
            raise TypeError(backing_value)
        self.name = name
        self.rial_type = rial_type
        self.access_modifier = access_modifier
        self.backing_value = backing_value
        self.sloc = sloc
        self.global_variable = isinstance(self.backing_value, GlobalValue)

    def __str__(self):
        return f"{self.access_modifier} {self.name}: {self.rial_type} = {self.llvm_type}"

    @property
    @lru_cache(1)
    def llvm_type(self):
        if self.rial_type == "Function":
            var = self.backing_value.type.pointee
            while isinstance(var.pointee, ir.PointerType):
                var = var.pointee
            return var

        from rial.ParserState import ParserState
        return ParserState.map_type_to_llvm_no_pointer(self.rial_type)

    @property
    @lru_cache(1)
    def llvm_type_as_function_arg(self):
        from rial.ParserState import ParserState
        return ParserState.map_type_to_llvm(self.rial_type)

    @property
    def value_for_calculations(self):
        from rial.metadata.RIALFunction import RIALFunction

        if self.is_pointer and not isinstance(self.backing_value.type.pointee, RIALFunction):
            from rial.ParserState import ParserState
            return ParserState.llvmgen().builder.load(self.backing_value)
        return self.backing_value

    @property
    def value_for_assignment(self):
        from rial.ParserState import ParserState
        builder = ParserState.llvmgen().builder
        if isinstance(self.backing_value, AllocaInstr):
            return builder.load(self.backing_value)
        if isinstance(self.backing_value, GEPInstr):
            return builder.load(self.backing_value)
        if isinstance(self.backing_value, Argument) and isinstance(self.backing_value, ir.PointerType):
            return builder.load(self.backing_value)
        if isinstance(self.backing_value, CastInstr) and isinstance(self.backing_value.operands[0].type,
                                                                    ir.PointerType):
            return builder.load(self.backing_value)
        if isinstance(self.backing_value, CallInstr) and isinstance(self.backing_value.callee.function_type.return_type,
                                                                    ir.PointerType):
            return builder.load(self.backing_value)

        return self.backing_value

    @property
    def is_pointer(self):
        """
        A RIALVariable is a pointer when:
        - it's an alloca instr or
        - it's a gep instr or
        - it's an argument that isn't a builtin
        :return:
        """
        return isinstance(self.backing_value, AllocaInstr) or isinstance(self.backing_value, GEPInstr) \
               or (isinstance(self.backing_value, Argument) and not is_builtin_type(self.rial_type))

    @property
    def value_is_integer(self):
        return self.rial_type.startswith("Int") and not is_array(self.rial_type)

    @property
    def points_to_primitive(self):
        return self.is_pointer and is_builtin_type(self.rial_type)

    @property
    def pointee_type(self):
        if isinstance(self.backing_value, AllocaInstr) or isinstance(self.backing_value, Argument):
            return self.backing_value.type.pointee

        return None

    @property
    def is_allocated_variable(self):
        return isinstance(self.backing_value, AllocaInstr) or (
                isinstance(self.backing_value, Argument) and isinstance(self.backing_value.type, PointerType))

    @property
    def is_void(self):
        return isinstance(self.llvm_type, ir.VoidType)

    def value_for_rial_type(self, rial_type: str):
        """
        Loads the backing value if the :rial_type: is a builtin (primitive) type and returns the backing_value as is if not.
        :param rial_type:
        :return:
        """
        # Primitives
        if is_builtin_type(rial_type):
            return self.value_for_assignment

        if rial_type == "CString" and self.rial_type == "CString":
            if isinstance(self.backing_value.type.pointee, ir.PointerType):
                from rial.ParserState import ParserState
                builder = ParserState.llvmgen().builder
                return builder.load(self.backing_value)

        return self.backing_value

    @property
    def rial_type_of_array_element(self):
        return self.rial_type.replace("[]", "")
