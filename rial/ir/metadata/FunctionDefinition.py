from typing import List

from rial.ir.RIALVariable import RIALVariable
from rial.ir.modifier.AccessModifier import AccessModifier


class FunctionDefinition:
    rial_return_type: str
    access_modifier: AccessModifier
    rial_args: List[RIALVariable]
    struct: str
    unsafe: bool

    def __init__(self, rial_return_type: str = "", access_modifier: AccessModifier = AccessModifier.PRIVATE,
                 rial_args: List[RIALVariable] = None, struct="", unsafe: bool = False):
        self.rial_return_type = rial_return_type
        self.access_modifier = access_modifier
        self.rial_args = rial_args
        self.struct = struct
        self.unsafe = unsafe

        if self.rial_args is None:
            self.rial_args = list()
