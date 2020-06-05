from typing import List

from llvmlite import ir

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import NULL, TRUE, FALSE, convert_number_to_constant, map_llvm_to_type
from rial.concept.parser import Transformer_InPlaceRecursive, Discard
from rial.rial_types.RIALVariable import RIALVariable
from rial.util import good_hash


class PrimitiveASTTransformer(Transformer_InPlaceRecursive):
    llvmgen: LLVMGen

    def __init__(self):
        super().__init__()
        self.llvmgen = ParserState.llvmgen()
