from dataclasses import dataclass
from typing import List, Dict, Optional

from llvmlite.ir import Function

from rial.mir.FunctionDefinition import FunctionDefinition
from rial.mir.GlobalDefinition import GlobalDefinition
from rial.mir.MIRConstruct import MIRConstruct


@dataclass
class Module(MIRConstruct):
    """
    :ivar function_map: Map of function definition in MIR to Function declaration in IR
    """
    filename: str
    directory: str
    name: str
    globs: List[GlobalDefinition] = None
    functions: List[FunctionDefinition] = None
    function_map: Dict[FunctionDefinition, Function] = None

    def __post_init__(self):
        if self.globs is None:
            self.globs = list()
        if self.functions is None:
            self.functions = list()
        if self.function_map is None:
            self.function_map = dict()

    def is_builtin_module(self):
        return self.name.startswith('rial:builtin:')

    def get_global_definition(self, name: str) -> Optional[GlobalDefinition]:
        return next((glob for glob in self.globs if glob.name == name), None)
