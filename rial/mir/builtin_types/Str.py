from dataclasses import dataclass

from rial.mir.BuiltinType import BuiltinType


@dataclass
class Str(BuiltinType):
    name: str = "Str"
