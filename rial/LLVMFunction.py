from typing import List, Tuple

from llvmlite.ir import FunctionType

from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class LLVMFunction:
    name: str
    function_type: FunctionType
    access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE
    module: str
    rial_return_type: str
    rial_args: List[Tuple[str, str]]

    def __init__(self, name: str, function_type: FunctionType, access_modifier: RIALAccessModifier, module: str,
                 rial_return_type: str, rial_args: List[Tuple[str, str]], ):
        self.name = name
        self.function_type = function_type
        self.access_modifier = access_modifier
        self.module = module
        self.rial_return_type = rial_return_type
        self.rial_args = rial_args
