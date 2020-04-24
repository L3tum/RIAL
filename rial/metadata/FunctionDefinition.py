from typing import Tuple, List

from llvmlite.ir import MDValue

from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class FunctionDefinition:
    rial_return_type: str
    access_modifier: RIALAccessModifier
    rial_args: List[Tuple[str, str]]
    struct: str

    def __init__(self, rial_return_type: str = "", access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE,
                 rial_args: List[Tuple[str, str]] = None, struct=""):
        self.rial_return_type = rial_return_type
        self.access_modifier = access_modifier
        self.rial_args = rial_args
        self.struct = struct

        if self.rial_args is None:
            self.rial_args = list()

    def to_list(self):
        return [self.rial_return_type, str(self.access_modifier), self.rial_args, self.struct]

    @staticmethod
    def from_mdvalue(value: MDValue):
        definition = FunctionDefinition()
        definition.rial_return_type = value.operands[0].operands[0].string
        definition.access_modifier = RIALAccessModifier(value.operands[0].operands[1].string)
        definition.struct = value.operands[0].operands[3].string
        # TODO: RIAL Args parsing

        return definition
