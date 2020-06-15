from dataclasses import dataclass
from typing import Any

from rial.mir.MIRConstruct import MIRConstruct
from rial.mir.Type import Type


@dataclass
class Value(MIRConstruct):
    type: Type
    value: Any
