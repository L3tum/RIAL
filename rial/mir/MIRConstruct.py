from dataclasses import dataclass
from typing import List

from rial.mir.SourceSpan import SourceSpan


@dataclass
class MIRConstruct:
    source_span: SourceSpan

    def _to_string(self, buf: List[str]):
        raise NotImplementedError()
