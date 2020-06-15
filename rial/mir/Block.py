from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from rial.mir.MIRConstruct import MIRConstruct


class BlockKind(Enum):
    BASIC_BLOCK = "basic"
    CONDITIONAL_BLOCK = "conditional"
    LOOPED_BLOCK = "loop"
    FUNC_TERMINATOR = "terminator"
    FUNC_ENTRY = "entry"


@dataclass
class Block(MIRConstruct):
    kind: BlockKind = BlockKind.BASIC_BLOCK
    named_values: Dict[str, MIRConstruct] = None
    parent: Optional[MIRConstruct] = None

    def __post_init__(self):
        if self.named_values is None:
            self.named_values = dict()

    def get_named_value(self, name: str) -> Optional[MIRConstruct]:
        current: Block = self
        while True:
            if current is None:
                break
            if name in current.named_values:
                return current.named_values[name]
            current: Block = current.parent

        return None

    def add_named_value(self, name: str, value: MIRConstruct):
        """
        Raises KeyError
        :raises KeyError:
        :param name:
        :param value:
        :return:
        """
        if name in self.named_values:
            raise KeyError()

        self.named_values[name] = value
