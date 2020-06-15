from dataclasses import dataclass
from typing import Optional

from rial.mir.BuiltinType import BuiltinType
from rial.mir.Type import Type


@dataclass
class Null(BuiltinType):
    wrapping_type: Optional[Type] = None
