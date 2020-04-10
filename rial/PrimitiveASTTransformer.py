import base64

from llvmlite import ir
from llvmlite.ir import GlobalVariable

from rial.LLVMGen import LLVMGen
from rial.builtin_type_to_llvm_mapper import NULL, TRUE, FALSE
from rial.concept.parser import Transformer_InPlaceRecursive


class PrimitiveASTTransformer(Transformer_InPlaceRecursive):
    llvmgen: LLVMGen

    def init(self, llvmgen: LLVMGen):
        self.llvmgen = llvmgen

    def null(self, nodes):
        return NULL

    def true(self, nodes):
        return TRUE

    def false(self, nodes):
        return FALSE

    def number(self, nodes):
        return self.llvmgen.gen_integer(int(nodes[0].value), 32)

    def string(self, nodes) -> GlobalVariable:
        value = nodes[0].value.strip("\"")
        name = ".const.string.%s" % base64.standard_b64encode(value.encode())
        glob = None

        if any(global_variable == name for global_variable in self.llvmgen.global_variables.keys()):
            glob = self.llvmgen.global_variables.get(name)
        else:
            glob = self.llvmgen.gen_string_lit(name, value)
            self.llvmgen.global_variables[name] = glob

        # Get pointer to first element
        # TODO: Change to return array and check in method signature for c-type stringiness
        return glob.gep([ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
