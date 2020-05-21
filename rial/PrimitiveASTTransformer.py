from typing import List

from llvmlite import ir
from llvmlite.ir import GlobalVariable

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import NULL, TRUE, FALSE, convert_number_to_constant
from rial.concept.parser import Transformer_InPlaceRecursive, Discard
from rial.util import good_hash


class PrimitiveASTTransformer(Transformer_InPlaceRecursive):
    llvmgen: LLVMGen

    def __init__(self):
        super().__init__()
        self.llvmgen = LLVMGen()

    def using(self, nodes):
        mod_name = ':'.join([node.value for node in nodes])
        ParserState.add_dependency_and_wait(mod_name)
        raise Discard()

    def null(self, nodes):
        return NULL

    def true(self, nodes):
        return TRUE

    def false(self, nodes):
        return FALSE

    def number(self, nodes: List):
        value: str = nodes[0].value
        return convert_number_to_constant(value)

    def string(self, nodes) -> GlobalVariable:
        value = nodes[0].value.strip("\"")
        name = ".const.string.%s" % good_hash(value)
        glob = self.llvmgen.gen_string_lit(name, value)

        # Get pointer to first element
        # TODO: Change to return array and check in method signature for c-type stringiness
        return glob.gep([ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
