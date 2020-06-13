from typing import Optional

from llvmlite import ir

from rial.ir.modifier.AccessModifier import AccessModifier
from rial.transformer.builtin_type_to_llvm_mapper import map_shortcut_to_type


class RIALVariable:
    identified_variable: bool
    rial_type: str
    llvm_type: ir.Type
    value: ir.Value
    name: str
    access_modifier: AccessModifier

    def __init__(self, name: str, rial_type: str, llvm_type: ir.Type, value: Optional[ir.Value],
                 access_modifier: AccessModifier = AccessModifier.PRIVATE, identified_variable: bool = False):
        assert isinstance(name, str)
        assert isinstance(rial_type, str)
        assert isinstance(llvm_type, ir.Type)
        assert value is None or isinstance(value, ir.Value)
        assert isinstance(access_modifier, AccessModifier)

        self.name = name
        self.rial_type = map_shortcut_to_type(rial_type)
        self.llvm_type = llvm_type
        self.value = value
        self.access_modifier = access_modifier
        self.identified_variable = identified_variable

    @property
    def is_global(self):
        return isinstance(self.value, ir.GlobalValue)

    @property
    def is_variable(self):
        if isinstance(self.value, ir.AllocaInstr):
            return True
        if isinstance(self.value, ir.GlobalVariable):
            return True
        if isinstance(self.value, ir.GEPInstr) and isinstance(self.value.type, ir.PointerType):
            return True
        if isinstance(self.value, ir.CastInstr) and (self.value.opname == "bitcast" or self.value.opname == "inttoptr"):
            return True
        if isinstance(self.value, ir.Argument) and isinstance(self.value.type, ir.PointerType):
            return True
        if isinstance(self.value, ir.CallInstr) and isinstance(self.value.callee, ir.Function) and isinstance(
                self.value.callee.function_type.return_type, ir.PointerType):
            return True
        return False

    def get_loaded_if_variable(self, module):
        return self.is_variable and module.builder.load(self.value) or self.value

    @property
    def array_element_type(self):
        return self.rial_type.split('[')[0]

    def __str__(self):
        return f"{self.name}: {self.rial_type}/{self.llvm_type}: {self.value} [{self.access_modifier}]"

    def __repr__(self):
        return self.__str__()
