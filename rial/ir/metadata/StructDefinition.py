from typing import Dict, Tuple, List

from rial.ir.RIALVariable import RIALVariable
from rial.ir.modifier.AccessModifier import AccessModifier


class StructDefinition:
    access_modifier: AccessModifier
    properties: Dict[str, Tuple[int, RIALVariable]]
    base_structs: List[str]

    def __init__(self, access_modifier: AccessModifier = None,
                 properties: Dict[str, Tuple[int, RIALVariable]] = None,
                 base_structs: List[str] = None):
        self.access_modifier = access_modifier
        self.properties = properties
        self.base_structs = base_structs

        if self.properties is None:
            self.properties = dict()

        if self.base_structs is None:
            self.base_structs = list()
