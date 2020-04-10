from typing import Dict, Optional, List

from rial.LLVMFunction import LLVMFunction
from rial.LLVMStruct import LLVMStruct


class ParserState(object):
    functions: Dict[str, LLVMFunction]
    implemented_functions: List[str]
    structs: Dict[str, LLVMStruct]

    def __init__(self):
        self.functions = dict()
        self.implemented_functions = list()
        self.structs = dict()

    def search_function(self, name: str) -> Optional[LLVMFunction]:
        if name in self.functions:
            return self.functions[name]

        return None

    def search_implemented_functions(self, name: str) -> bool:
        return name in self.implemented_functions

    def search_structs(self, name: str) -> Optional[LLVMStruct]:
        if name in self.structs:
            return self.structs[name]

        return None
