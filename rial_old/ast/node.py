from rial_old.parser_state import ParserState

class Node:
    ps: ParserState

    def __init__(self, ps: ParserState):
        self.ps = ps

    def eval(self):
        return ""
