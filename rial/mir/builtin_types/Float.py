from dataclasses import dataclass

from rial.mir.BuiltinType import BuiltinType


@dataclass
class Float(BuiltinType):
    name: str = "Float"
