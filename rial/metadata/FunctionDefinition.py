from typing import Tuple, List

from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class FunctionDefinition:
    rial_return_type: str
    access_modifier: RIALAccessModifier
    """
    Tuple of type -> name
    """
    rial_args: List[Tuple[str, str]]
    struct: str
    unsafe: bool

    def __init__(self, rial_return_type: str = "", access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE,
                 rial_args: List[Tuple[str, str]] = None, struct="", unsafe: bool = False):
        self.rial_return_type = rial_return_type
        self.access_modifier = access_modifier
        self.rial_args = rial_args
        self.struct = struct
        self.unsafe = unsafe

        if self.rial_args is None:
            self.rial_args = list()
