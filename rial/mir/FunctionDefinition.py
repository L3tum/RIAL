from dataclasses import dataclass
from typing import List

from rial.ir.modifier.AccessModifier import AccessModifier
from rial.mir.Block import Block
from rial.mir.FunctionArgument import FunctionArgument
from rial.mir.MIRConstruct import MIRConstruct
from rial.mir.Type import Type


@dataclass
class FunctionDefinition(MIRConstruct):
    name: str
    arguments: List[FunctionArgument]
    return_type: Type
    attributes: List[str]
    unsafe: bool = False
    access_modifier: AccessModifier = AccessModifier.PRIVATE
    blocks: List[Block] = None

    def __post_init__(self):
        if self.blocks is None:
            self.blocks = list()
