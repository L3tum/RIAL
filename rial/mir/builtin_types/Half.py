from dataclasses import dataclass

from rial.mir.BuiltinType import BuiltinType


@dataclass
class Half(BuiltinType):
    name: str = "Half"
