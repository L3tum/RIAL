import sys

from llvmlite import ir

from rial_old.ast.node import Node
from rial_old.parser_state import ParserState


class StringLiteral(Node):
    value: str

    def __init__(self, ps: ParserState, value: str):
        super().__init__(ps)
        self.value = value.replace("\\n", "\n").replace("\\0", "\0")

    def eval(self):
        glob = None
        if any(global_variable == self.value for global_variable in self.ps.global_variables.keys()):
            glob = self.ps.global_variables.get(self.value)
        else:
            const_char_arr = ir.Constant(ir.ArrayType(ir.IntType(8), len(self.value)),
                                         bytearray(self.value.encode("utf8")))
            glob = ir.GlobalVariable(self.ps.module, const_char_arr.type, name="str")
            glob.linkage = 'internal'
            glob.global_constant = True
            glob.initializer = const_char_arr
            self.ps.global_variables[self.value] = glob
        return self.ps.builder.bitcast(glob, ir.IntType(8).as_pointer())
