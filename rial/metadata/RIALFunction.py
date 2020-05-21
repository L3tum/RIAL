from llvmlite.ir import Function, FunctionType

from rial.metadata.FunctionDefinition import FunctionDefinition


class RIALFunction(Function):
    canonical_name: str
    definition: FunctionDefinition

    def __init__(self, module, ftype: FunctionType, name: str, canonical_name: str):
        super().__init__(module, ftype, name)
        self.definition = None
        self.canonical_name = canonical_name
