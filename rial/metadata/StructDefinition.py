from typing import Dict, Tuple, List

from rial.metadata.RIALFunction import RIALFunction
from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class StructDefinition:
    access_modifier: RIALAccessModifier
    properties: Dict[str, Tuple[int, RIALVariable]]
    functions: List[RIALFunction]
    base_structs: List[str]

    def __init__(self, access_modifier: RIALAccessModifier = None,
                 properties: Dict[str, Tuple[int, RIALVariable]] = None, functions: List[RIALFunction] = None,
                 base_structs: List[str] = None):
        self.access_modifier = access_modifier
        self.properties = properties
        self.functions = functions
        self.base_structs = base_structs

        if self.properties is None:
            self.properties = dict()

        if self.functions is None:
            self.functions = list()

        if self.base_structs is None:
            self.base_structs = list()
