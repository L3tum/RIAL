from llvmlite.ir import Instruction

from rial_old.ast.node import Node
from rial_old.parser_state import ParserState


class BinaryOP(Node):
    left: Node
    right: Node

    def __init__(self, ps: ParserState, left: Node, right: Node):
        super().__init__(ps)
        self.left = left
        self.right = right


class Sum(BinaryOP):
    def eval(self) -> Instruction:
        return self.ps.builder.add(self.left.eval(), self.right.eval())


class Sub(BinaryOP):
    def eval(self) -> Instruction:
        return self.ps.builder.sub(self.left.eval(), self.right.eval())


class Mul(BinaryOP):
    def eval(self) -> Instruction:
        return self.ps.builder.mul(self.left.eval(), self.right.eval())


class Div(BinaryOP):
    def eval(self) -> Instruction:
        return self.ps.builder.sdiv(self.left.eval(), self.right.eval())
