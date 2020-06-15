from typing import List

from rial.concept.parser import Token


class SourceSpan:
    start_col: int
    start_line: int
    end_col: int
    end_line: int

    def __init__(self, start_col: int, start_line: int, end_col: int, end_line: int):
        self.start_col = start_col
        self.start_line = start_line
        self.end_col = end_col
        self.end_line = end_line

    @staticmethod
    def from_token(token):
        token: Token

        return SourceSpan(token.column, token.line, token.end_column, token.end_line)

    @staticmethod
    def from_tokens(tokens: List):
        tokens: List[Token]

        assert len(tokens) > 0

        return SourceSpan(tokens[0].column, tokens[0].line, tokens[-1].end_column, tokens[-1].end_line)
