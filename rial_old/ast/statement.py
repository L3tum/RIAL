from rial_old.ast.node import Node
from rial_old.parser_state import ParserState


class Statement(Node):
    expression: Node

    def __init__(self, ps: ParserState, expression: Node):
        super().__init__(ps)
        self.expression = expression

    def eval(self):
        return self.expression.eval()
