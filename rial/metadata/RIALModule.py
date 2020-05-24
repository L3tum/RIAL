from typing import List, Optional

from llvmlite.ir import Module, context

from rial.metadata.RIALFunction import RIALFunction
from rial.metadata.RIALIdentifiedStructType import RIALIdentifiedStructType


class RIALModule(Module):
    dependencies: List[str]
    structs: List[RIALIdentifiedStructType]
    global_variables: List  # List of RIALVariables, see if we still need it in a second
    filename: str

    def __init__(self, name='', context=context.global_context):
        super().__init__(name, context)
        self.dependencies = list()
        self.structs = list()
        self.global_variables = list()
        self.filename = ""

    def get_global_safe(self: Module, name: str) -> Optional[RIALFunction]:
        try:
            return self.get_global(name)
        except KeyError:
            return None

    def get_function(self, name: str) -> Optional[RIALFunction]:
        return next((func for func in self.functions if func.canonical_name == name), None)

    def get_rial_variable(self, name: str):
        return next((glob for glob in self.global_variables if glob.name == name), None)
