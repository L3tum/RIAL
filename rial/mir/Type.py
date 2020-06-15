from dataclasses import dataclass

from rial.mir.MIRConstruct import MIRConstruct


@dataclass
class Type(MIRConstruct):
    name: str
