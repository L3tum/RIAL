from dataclasses import dataclass
from typing import List

from rial.mir.MIRConstruct import MIRConstruct
from rial.mir.Type import Type
from rial.mir.Value import Value


@dataclass
class VariableDefinition(MIRConstruct):
    name: str
    value: Value
    type: Type = None
    reads: List[MIRConstruct] = None
    writes: List[MIRConstruct] = None

    def __post_init__(self):
        if self.type is None:
            self.type = self.value.type
        if self.reads is None:
            self.reads = list()

        if self.writes is None:
            self.writes = list()
