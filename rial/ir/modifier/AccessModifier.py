from enum import Enum


class AccessModifier(Enum):
    PRIVATE = "private"
    INTERNAL = "internal"
    PUBLIC = "public"

    def __repr__(self):
        return self.value

    def __str__(self):
        return self.__repr__()

    def __lt__(self, other):
        if self == AccessModifier.PRIVATE and (
                other == AccessModifier.INTERNAL or other == AccessModifier.PUBLIC):
            return True
        if self == AccessModifier.INTERNAL and other == AccessModifier.PUBLIC:
            return True

        return False

    def get_linkage(self):
        return self == AccessModifier.PRIVATE and "private" or "external"
