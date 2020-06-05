from typing import Dict, Any

from rial.concept.parser import Token


class MetadataToken(Token):
    metadata: Dict[str, Any]

    def __init__(self, ty, value):
        super().__new__(Token, ty, value)
        self.metadata = dict()
