from llvmlite.ir import IdentifiedStructType

from rial.metadata.StructDefinition import StructDefinition


class RIALIdentifiedStructType(IdentifiedStructType):
    definition: StructDefinition
    module_name: str

    def __init__(self, context, name, packed=False):
        super().__init__(context, name, packed)
        self.definition = None
        self.module_name = ""
