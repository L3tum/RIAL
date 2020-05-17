from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class RIALFunctionDeclarationModifier:
    access_modifier: RIALAccessModifier
    unsafe: bool

    def __init__(self, access_modifier: RIALAccessModifier = RIALAccessModifier.INTERNAL, unsafe: bool = False):
        self.access_modifier = access_modifier
        self.unsafe = unsafe
