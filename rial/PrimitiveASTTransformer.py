from typing import List

from llvmlite import ir

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import NULL, TRUE, FALSE, convert_number_to_constant, map_llvm_to_type
from rial.concept.parser import Transformer_InPlaceRecursive, Discard, Token
from rial.metadata.RIALModule import RIALModule
from rial.rial_types.RIALVariable import RIALVariable
from rial.util import good_hash


class PrimitiveASTTransformer(Transformer_InPlaceRecursive):
    module: RIALModule
    llvmgen: LLVMGen

    def __init__(self):
        super().__init__()
        self.llvmgen = ParserState.llvmgen()
        self.module = ParserState.module()

    def using(self, nodes):
        mod_name = ':'.join([node.value for node in nodes])
        ParserState.add_dependency_and_wait(mod_name)
        raise Discard()

    def null(self, nodes) -> RIALVariable:
        return RIALVariable("null", "UInt8", NULL)

    def true(self, nodes) -> RIALVariable:
        return RIALVariable("true", "Int1", TRUE)

    def false(self, nodes) -> RIALVariable:
        return RIALVariable("false", "Int1", FALSE)

    def number(self, nodes: List[Token]) -> RIALVariable:
        value: str = nodes[0].value
        constant = convert_number_to_constant(value)
        return RIALVariable("number", map_llvm_to_type(constant.type), constant, sloc=(nodes[0].line, nodes[0].column))

    def string(self, nodes) -> RIALVariable:
        value = nodes[0].value.strip("\"")
        name = ".const.string.%s" % good_hash(value)
        glob = self.llvmgen.gen_string_lit(name, value)

        # TODO: Change to return array and check in method signature for c-type stringiness
        return RIALVariable(name, "CString", glob.gep([ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)]),
                            sloc=(nodes[0].line, nodes[0].column))
        # Get pointer to first element
        # return glob.gep([ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
