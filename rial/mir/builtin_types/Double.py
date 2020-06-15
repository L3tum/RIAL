from dataclasses import dataclass

from rial.mir.BuiltinType import BuiltinType


@dataclass
class Double(BuiltinType):
    name: str = "Double"
