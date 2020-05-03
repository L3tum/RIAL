from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class RIALFunctionDeclarationModifier:
    access_modifier: RIALAccessModifier

    def __init__(self, access_modifier: RIALAccessModifier = RIALAccessModifier.INTERNAL):
        self.access_modifier = access_modifier
