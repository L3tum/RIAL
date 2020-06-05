from typing import List

from rial.ir.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.ir.RIALModule import RIALModule
from rial.ir.RIALVariable import RIALVariable
from rial.ir.metadata.StructDefinition import StructDefinition
from rial.ir.modifier.AccessModifier import AccessModifier


def create_identified_struct_type(module: RIALModule, name: str, access_modifier: AccessModifier,
                                  base_structs: List[RIALIdentifiedStructType],
                                  body: List[RIALVariable]) -> RIALIdentifiedStructType:
    assert isinstance(module, RIALModule)
    assert isinstance(name, str)
    assert isinstance(access_modifier, AccessModifier)
    assert isinstance(base_structs, List)
    assert isinstance(body, List)

    struct = module.context.get_identified_type(name)
    rial_struct = RIALIdentifiedStructType(struct.context, name, struct.packed)
    module.context.identified_types[name] = rial_struct
    struct = rial_struct
    struct_def = StructDefinition(access_modifier)

    # Build body
    props_def = dict()
    props = list()
    prop_offset = 0
    for base_struct in base_structs:
        for prop in base_struct.definition.properties.values():
            props.append(prop[1].llvm_type)
            props_def[prop[1].name] = (prop_offset, prop[1])
            prop_offset += 1

        struct_def.base_structs.append(base_struct.name)

    for bod in body:
        props.append(bod.llvm_type)
        props_def[bod.name] = (prop_offset, bod)
        prop_offset += 1

    struct.set_body(*tuple(props))
    struct.module_name = module.name
    struct_def.properties = props_def
    struct.definition = struct_def

    return struct
