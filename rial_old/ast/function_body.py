from typing import List

from rial_old.ast.node import Node
from rial_old.ast.statement import Statement
from rial_old.parser_state import ParserState


class FunctionBody(Node):
    statements: List[Statement]

    def __init__(self, ps: ParserState):
        super().__init__(ps)
        self.statements = list()

    def add_statement(self, statement: Statement):
        self.statements.append(statement)

    def eval(self):
        for statement in self.statements:
            statement.eval()
