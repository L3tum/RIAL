import base64
from typing import List

from llvmlite import ir
from llvmlite.ir import GlobalVariable

from rial.SingleParserState import SingleParserState
from rial.builtin_type_to_llvm_mapper import NULL, TRUE, FALSE
from rial.compilation_manager import CompilationManager
from rial.concept.parser import Transformer_InPlaceRecursive, Token
from rial.log import log_warn


class PrimitiveASTTransformer(Transformer_InPlaceRecursive):
    sps: SingleParserState

    def init(self, sps: SingleParserState):
        self.sps = sps

    def using(self, nodes):
        mod_name = ':'.join(nodes)
        CompilationManager.request_module(mod_name)
        self.sps.usings.append(mod_name)

    def null(self, nodes):
        return NULL

    def true(self, nodes):
        return TRUE

    def false(self, nodes):
        return FALSE

    def number(self, nodes: List[Token]):
        value: str = nodes[0].value
        value.replace("_", "")

        if "." in value or "e" in value:
            if value.endswith("f"):
                return self.sps.llvmgen.gen_float(float(value.strip("f")))
            return self.sps.llvmgen.gen_double(float(value.strip("d")))

        if value.startswith("0x"):
            return self.sps.llvmgen.gen_integer(int(value), 32)

        if value.startswith("0b"):
            return self.sps.llvmgen.gen_integer(int(value), 32)

        if value.endswith("l"):
            log_warn(
                f"{self.sps.llvmgen.module.name}[{nodes[0].line}:{nodes[0].column}] WARNING 0001")
            log_warn("Some fonts display a lowercase 'l' as a one. Please consider using an uppercase 'L' instead.")
            log_warn(value)
            value.lower()

        if value.endswith("l"):
            return self.sps.llvmgen.gen_integer(int(value.strip("l")), 64)

        return self.sps.llvmgen.gen_integer(int(nodes[0].value), 32)

    def string(self, nodes) -> GlobalVariable:
        value = nodes[0].value.strip("\"")
        name = ".const.string.%s" % base64.standard_b64encode(value.encode())
        glob = None

        if any(global_variable == name for global_variable in self.sps.llvmgen.global_variables.keys()):
            glob = self.sps.llvmgen.global_variables.get(name)
        else:
            glob = self.sps.llvmgen.gen_string_lit(name, value)
            self.sps.llvmgen.global_variables[name] = glob

        # Get pointer to first element
        # TODO: Change to return array and check in method signature for c-type stringiness
        return glob.gep([ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])
