from dataclasses import dataclass

from rial.ir.modifier.AccessModifier import AccessModifier
from rial.mir.VariableDefinition import VariableDefinition


@dataclass
class GlobalDefinition(VariableDefinition):
    access_modifier: AccessModifier = AccessModifier.PRIVATE
    linkage: str = None

    def __post_init__(self):
        if self.linkage is None:
            self.linkage = self.access_modifier.get_linkage()
