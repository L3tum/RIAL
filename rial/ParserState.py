from typing import Dict, Optional, List

from rial.LLVMFunction import LLVMFunction
from rial.LLVMStruct import LLVMStruct


class ParserState:
    functions: Dict[str, LLVMFunction]
    implemented_functions: List[str]
    structs: Dict[str, LLVMStruct]
    main_function: LLVMFunction

    def __init__(self):
        raise PermissionError()

    @staticmethod
    def init():
        ParserState.functions = dict()
        ParserState.implemented_functions = list()
        ParserState.structs = dict()

    @staticmethod
    def search_function(name: str) -> Optional[LLVMFunction]:
        if name in ParserState.functions:
            return ParserState.functions[name]

        return None

    @staticmethod
    def search_implemented_functions(name: str) -> bool:
        return name in ParserState.implemented_functions

    @staticmethod
    def search_structs(name: str) -> Optional[LLVMStruct]:
        if name in ParserState.structs:
            return ParserState.structs[name]

        return None
