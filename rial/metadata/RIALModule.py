from typing import List, Dict, Optional

from llvmlite.ir import Module, context

from rial.metadata.RIALFunction import RIALFunction
from rial.metadata.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.rial_types.RIALVariable import RIALVariable


class RIALModule(Module):
    dependencies: List[str]
    builtin_type_methods: Dict[str, List[str]]
    structs: List[RIALIdentifiedStructType]
    global_variables: List[RIALVariable]

    def __init__(self, name='', context=context.global_context):
        super().__init__(name, context)
        self.dependencies = list()
        self.builtin_type_methods = dict()
        self.structs = list()
        self.global_variables = list()

    def get_global_safe(self: Module, name: str) -> Optional[RIALFunction]:
        try:
            return self.get_global(name)
        except KeyError:
            return None

    def add_builtin_method(self, ty: str, method: str):
        if not ty in self.builtin_type_methods:
            self.builtin_type_methods[ty] = list()
        if not method in self.builtin_type_methods[ty]:
            self.builtin_type_methods[ty].append(method)

    def get_rial_variable(self, name: str):
        return next((glob for glob in self.global_variables if glob.name == name), None)
