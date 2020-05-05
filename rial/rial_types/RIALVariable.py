from llvmlite.ir import Value, GlobalValue

from rial.rial_types.RIALAccessModifier import RIALAccessModifier


# TODO: Use to implement variables and not just struct and global variables
class RIALVariable:
    name: str
    rial_type: str
    access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE
    backing_value: Value
    global_variable: bool
    module_name: str

    def __init__(self, name: str, module_name: str, rial_type: str, backing_value: Value,
                 access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE):
        self.name = name
        self.module_name = module_name
        self.rial_type = rial_type
        self.access_modifier = access_modifier
        self.backing_value = backing_value
        self.global_variable = isinstance(self.backing_value, GlobalValue)
