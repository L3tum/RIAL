from typing import Optional

from llvmlite import ir

from rial.ir.modifier.AccessModifier import AccessModifier
from rial.transformer.builtin_type_to_llvm_mapper import map_shortcut_to_type, is_builtin_type


class RIALVariable:
    rial_type: str
    llvm_type: ir.Type
    value: ir.Value
    name: str
    access_modifier: AccessModifier

    def __init__(self, name: str, rial_type: str, llvm_type: ir.Type, value: Optional[ir.Value],
                 access_modifier: AccessModifier = AccessModifier.PRIVATE):
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

    @property
    def is_global(self):
        return isinstance(self.value, ir.GlobalValue)

    @property
    def is_variable(self):
        return isinstance(self.value, ir.AllocaInstr) or \
               isinstance(self.value, ir.GlobalValue) or \
               isinstance(self.value, ir.GEPInstr) or \
               (isinstance(self.value, ir.CastInstr) and (
                       self.value.opname == "bitcast" or self.value.opname == "inttoptr")) or \
               (isinstance(self.value, ir.Argument) and not is_builtin_type(self.rial_type))

    def get_loaded_if_variable(self, module):
        return self.is_variable and module.builder.load(self.value) or self.value

    @property
    def array_element_type(self):
        return self.rial_type.split('[')[0]
