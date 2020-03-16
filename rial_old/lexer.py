from rply import LexerGenerator
from rial_old.tokens import tokens


class Lexer:
    lexer: LexerGenerator

    def __init__(self):
        lexer = LexerGenerator()

        for token in tokens:
            lexer.add(token.Key, token.Value)

        # Ignore whitespaces
        lexer.ignore(r'\s+')
        self.lexer = lexer

    def get_lexer(self):
        return self.lexer.build()
