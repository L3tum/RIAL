from dataclasses import dataclass
from typing import Optional

from rial.mir.BuiltinType import BuiltinType
from rial.mir.MIRConstruct import MIRConstruct
from rial.mir.Type import Type


@dataclass
class FunctionArgument(MIRConstruct):
    name: str
    spec_type: Type
    default_value: Optional[MIRConstruct] = None

    @property
    def passed_by_val(self):
        return isinstance(self.spec_type, BuiltinType)
