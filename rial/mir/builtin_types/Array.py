from dataclasses import dataclass
from typing import Union

from rial.mir.BuiltinType import BuiltinType
from rial.mir.Type import Type
from rial.mir.VariableDefinition import VariableDefinition


@dataclass
class Array(BuiltinType):
    name: str = "Array"
    type: Type = None
    count: Union[int, VariableDefinition] = None
