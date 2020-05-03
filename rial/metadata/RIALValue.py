from typing import Union

from llvmlite.ir import AllocaInstr, PointerType


class RIALValue:
    llvm_value: Union[AllocaInstr, PointerType]
    rial_type: str
    returned: bool
    references: int

    def __init__(self, llvm_value: Union[AllocaInstr, PointerType], rial_type: str, returned: bool = False,
                 references: int = 0):
        self.llvm_value = llvm_value
        self.rial_type = rial_type
        self.returned = returned
        self.references = references
