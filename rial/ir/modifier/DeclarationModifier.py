from rial.ir.modifier.AccessModifier import AccessModifier


class DeclarationModifier:
    access_modifier: AccessModifier
    unsafe: bool

    def __init__(self, access_modifier: AccessModifier, unsafe: bool):
        self.access_modifier = access_modifier
        self.unsafe = unsafe
