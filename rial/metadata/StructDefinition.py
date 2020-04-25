from typing import Dict, Tuple, List

from llvmlite.ir import MDValue

from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class StructDefinition:
    access_modifier: RIALAccessModifier
    properties: Dict[str, Tuple[int, RIALVariable]]
    functions: List[str]
    base_structs: List[str]

    def __init__(self, access_modifier: RIALAccessModifier = None,
                 properties: Dict[str, Tuple[int, RIALVariable]] = None, functions: List[str] = None,
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

    def to_list(self):
        prop_list = list()

        for key, prop in self.properties.items():
            prop: Tuple[int, RIALVariable]
            prop_list.append(
                [str(prop[0]), prop[1].name, str(prop[1].access_modifier), prop[1].rial_type,
                 str(prop[1].initial_value)])

        return [str(self.access_modifier), prop_list, self.functions, self.base_structs]

    @staticmethod
    def from_mdvalue(mdvalue: MDValue):
        struct_def = StructDefinition()
        struct_def.access_modifier = RIALAccessModifier(mdvalue.operands[0].operands[0].string)

        for op in mdvalue.operands[0].operands[1].operands:
            ops = op.operands
            struct_def.properties[ops[1].string] = (
                int(ops[0].string),
                RIALVariable(ops[1].string, ops[3].string, RIALAccessModifier(ops[2].string), initial_value=ops[4]))

        for op in mdvalue.operands[0].operands[2].operands:
            struct_def.functions.append(op.string)

        for op in mdvalue.operands[0].operands[3].operands:
            struct_def.base_structs.append(op.string)

        return struct_def
