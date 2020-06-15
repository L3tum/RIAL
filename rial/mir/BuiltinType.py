from dataclasses import dataclass

from rial.mir.SourceSpan import SourceSpan
from rial.mir.Type import Type


@dataclass
class BuiltinType(Type):
    name: str = ""
    source_span: SourceSpan = None
