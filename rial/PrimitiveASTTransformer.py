from typing import List

from llvmlite import ir
from llvmlite.ir import GlobalVariable

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import NULL, TRUE, FALSE
from rial.concept.parser import Transformer_InPlaceRecursive, Token, Discard
from rial.log import log_warn, log_warn_short
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

    def number(self, nodes: List[Token]):
        value: str = nodes[0].value
        value.replace("_", "")
        value_lowered = value.lower()

        if "." in value or "e" in value:
            if value.endswith("f"):
                return self.llvmgen.gen_float(float(value.strip("f")))
            if value.endswith("h"):
                return self.llvmgen.gen_half(float(value.strip("h")))
            return self.llvmgen.gen_double(float(value.strip("d")))

        if value.startswith("0x"):
            return self.llvmgen.gen_integer(int(value, 16), 32)

        if value.startswith("0b"):
            return self.llvmgen.gen_integer(int(value, 2), 32)

        if value.endswith("l"):
            log_warn(
                f"{ParserState.module().name}[{nodes[0].line}:{nodes[0].column}] WARNING 0001")
            log_warn_short(
                "Some fonts display a lowercase 'l' as a one. Please consider using an uppercase 'L' instead.")
            log_warn_short(value)

        if value_lowered.endswith("b"):
            return self.llvmgen.gen_integer(int(value_lowered.strip("b")), 8, True)

        if value_lowered.endswith("ul"):
            return self.llvmgen.gen_integer(int(value_lowered.strip("ul")), 64, True)

        if value_lowered.endswith("u"):
            return self.llvmgen.gen_integer(int(value_lowered.strip("u")), 32, True)

        if value_lowered.endswith("l"):
            return self.llvmgen.gen_integer(int(value_lowered.strip("l")), 64)

        return self.llvmgen.gen_integer(int(nodes[0].value), 32)

    def string(self, nodes) -> GlobalVariable:
        value = nodes[0].value.strip("\"")
        name = ".const.string.%s" % good_hash(value)
        glob = self.llvmgen.gen_string_lit(name, value)

        # Get pointer to first element
        # TODO: Change to return array and check in method signature for c-type stringiness
        return glob.gep([ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
