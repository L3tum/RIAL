from typing import List

from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class FunctionDefinition:
    rial_return_type: str
    access_modifier: RIALAccessModifier
    """
    Tuple of type -> name
    """
    rial_args: List[RIALVariable]
    struct: str
    unsafe: bool

    def __init__(self, rial_return_type: str = "", access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE,
                 rial_args: List[RIALVariable] = None, struct="", unsafe: bool = False):
        self.rial_return_type = rial_return_type
        self.access_modifier = access_modifier
        self.rial_args = rial_args
        self.struct = struct
        self.unsafe = unsafe

        if self.rial_args is None:
            self.rial_args = list()
