from typing import Optional, Dict, Tuple

from llvmlite.ir import BaseStructType, Function

from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class LLVMStruct:
    struct: BaseStructType
    name: str
    access_modifier: RIALAccessModifier
    properties: Dict[str, Tuple[int, RIALVariable]]
    constructor: Optional[Function]
    destructor: Optional[Function]

    def __init__(self, struct: BaseStructType, name: str, access_modifier: RIALAccessModifier):
        self.struct = struct
        self.name = name
        self.access_modifier = access_modifier
        self.properties = dict()
        self.constructor = None
        self.destructor = None
