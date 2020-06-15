from dataclasses import dataclass

from rial.mir.BuiltinType import BuiltinType


@dataclass
class Boolean(BuiltinType):
    name: str = "Boolean"
