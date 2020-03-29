from llvmlite.ir import FunctionType


class LLVMFunction:
    function_type: FunctionType
    access_modifier: str = "private"
    module: str

    def __init__(self, function_type: FunctionType, access_modifier: str, module: str):
        self.function_type = function_type
        self.access_modifier = access_modifier
        self.module = module
