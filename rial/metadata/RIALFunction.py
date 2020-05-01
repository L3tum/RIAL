from llvmlite.ir import Function

from rial.metadata.FunctionDefinition import FunctionDefinition


class RIALFunction(Function):
    definition: FunctionDefinition

    def __init__(self, module, ftype, name):
        super().__init__(module, ftype, name)
        self.definition = None
