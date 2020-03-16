from llvmlite import ir
from llvmlite.ir import Constant

from rial_old.ast.node import Node
from rial_old.parser_state import ParserState


class Number(Node):
    def __init__(self, ps: ParserState, value):
        super().__init__(ps)
        self.value = value

    def eval(self) -> Constant:
        return ir.Constant(ir.IntType(32), int(self.value))
