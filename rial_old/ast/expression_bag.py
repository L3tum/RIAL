from typing import List

from rial_old.ast.node import Node
from rial_old.parser_state import ParserState


class ExpressionBag(Node):
    expressions: List[Node]

    def __init__(self, ps: ParserState):
        super().__init__(ps)
        self.expressions = list()
