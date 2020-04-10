from enum import Enum


class RIALAccessModifier(Enum):
    PRIVATE = "private"
    INTERNAL = "internal"
    PUBLIC = "public"

    def __repr__(self):
        return self.value

    def __str__(self): return self.__repr__()

    def get_linkage(self):
        return self == RIALAccessModifier.PRIVATE and "private" or "external"
