from typing import List


class Token:
    Key: str
    Value: str

    def __init__(self, key: str, value: str):
        self.Key = key
        self.Value = value


tokens: List[Token] = [
    Token('OPEN_BRACES', r'\('),
    Token('CLOSE_BRACES', r'\)'),
    Token('OPEN_CURLY_BRACES', r'{'),
    Token('CLOSE_CURLY_BRACES', r'}'),
    Token('SEMI_COLON', r'\;'),
    Token('COLON', r'\:'),
    Token('SUM', r'\+'),
    Token('SUB', r'\-'),
    Token('MUL', r'\*'),
    Token('DIV', r'\/'),
    Token('EXTERNAL', r'external'),
    Token('PARAMS', r'params'),
    Token('COMMA', r','),
    Token('NUMBER', r'\d+'),
    Token('STRING_LIT', r'\".*\"'),
    Token('IDENTIFIER', r'[a-zA-Z]+\w*'),
]
