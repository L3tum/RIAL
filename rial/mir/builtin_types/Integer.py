from dataclasses import dataclass

from rial.mir.BuiltinType import BuiltinType


@dataclass
class Integer(BuiltinType):
    name: str = "Integer"
    bit_width: int = 32
    unsigned: bool = False
