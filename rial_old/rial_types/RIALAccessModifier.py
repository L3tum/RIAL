from enum import Enum


class RIALAccessModifier(Enum):
    PRIVATE = "private"
    INTERNAL = "internal"
    PUBLIC = "public"

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.__repr__()

    def __lt__(self, other):
        if self == RIALAccessModifier.PRIVATE and (
                other == RIALAccessModifier.INTERNAL or other == RIALAccessModifier.PUBLIC):
            return True
        if self == RIALAccessModifier.INTERNAL and other == RIALAccessModifier.PUBLIC:
            return True

        return False

    def get_linkage(self):
        return self == RIALAccessModifier.PRIVATE and "private" or "external"
