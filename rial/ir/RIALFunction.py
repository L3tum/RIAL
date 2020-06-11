from typing import List

from llvmlite.ir import Function, FunctionType

from rial.ir.LLVMBlock import LLVMBlock
from rial.ir.metadata.FunctionDefinition import FunctionDefinition


class RIALFunction(Function):
    canonical_name: str
    definition: FunctionDefinition
    blocks: List[LLVMBlock]

    def __init__(self, module, ftype: FunctionType, name: str, canonical_name: str):
        super().__init__(module, ftype, name)
        self.definition = None
        self.canonical_name = canonical_name

    def append_basic_block(self, name=''):
        blk = LLVMBlock(parent=self, name=name)
        self.blocks.append(blk)
        return blk
