from rial_old.ast.node import Node
from rial_old.parser_state import ParserState


class VariableDeclaration(Node):
    type: str
    name: str

    def __init__(self, ps: ParserState, type: str, name: str):
        super().__init__(ps)
        self.type = type
        self.name = name

    # TODO: Default eval implementation if the declaration is inside a function body
