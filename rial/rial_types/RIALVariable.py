from typing import Any

from llvmlite.ir import Type

from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class RIALVariable:
    name: str
    rial_type: str
    llvm_type: Type
    access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE
    initial_value: Any

    def __init__(self, name: str, rial_type: str, llvm_type: Type,
                 access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE, initial_value: Any = None):
        self.name = name
        self.rial_type = rial_type
        self.llvm_type = llvm_type
        self.access_modifier = access_modifier
        self.initial_value = initial_value
