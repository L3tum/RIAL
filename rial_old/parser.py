import sys
from typing import List

from rply import ParserGenerator, Token
from rply.parser import LRParser
from rply.parsergenerator import LRTable

from rial_old.ast.binary_operation import Sum, Sub, Mul, Div, BinaryOP
from rial_old.ast.expression_bag import ExpressionBag
from rial_old.ast.function_call import FunctionCall
from rial_old.ast.function_declaration import FunctionDeclaration
from rial_old.ast.node import Node
from rial_old.ast.number import Number
from rial_old.ast.function_body import FunctionBody
from rial_old.ast.program import Program
from rial_old.ast.statement import Statement
from rial_old.ast.string_literal import StringLiteral
from rial_old.ast.variable_declaration import VariableDeclaration
from rial_old.log import log_fail, log_warn
from rial_old.tokens import tokens
from rial_old.parser_state import ParserState


class Parser:
    pg: ParserGenerator

    def __init__(self):
        self.pg = ParserGenerator(
            [token.Key for token in tokens],
            # A list of precedence rules with ascending precedence, to
            # disambiguate ambiguous production rules.
            precedence=[
                ('left', ['COMMA']),
                ('left', ['SUM', 'SUB']),
                ('left', ['MUL', 'DIV'])
            ],
            cache_id="rial_old"
        )

        self._parse()

    def _parse(self):
        @self.pg.production('program : program function_decl')
        @self.pg.production('program : function_decl')
        def program(ps: ParserState, p) -> Program:
            prog: Program

            if len(p) == 2:
                prog = p[0]
                prog.functions.append(p[1])
            else:
                prog = Program(ps)
                prog.functions.append(p[0])

            return prog

        @self.pg.production(
            'function_decl : EXTERNAL expression OPEN_BRACES expression CLOSE_BRACES SEMI_COLON')
        @self.pg.production(
            'function_decl : EXTERNAL expression OPEN_BRACES CLOSE_BRACES SEMI_COLON')
        def external_function_decl(ps: ParserState, p) -> FunctionDeclaration:
            if not isinstance(p[1], VariableDeclaration):
                raise TypeError("Function declaration needs a type and a name")

            decl: VariableDeclaration = p[1]
            params: Node = None

            if isinstance(p[3], Node):
                params = p[3]

            return FunctionDeclaration(ps, decl.type, decl.name, params, True, None)

        @self.pg.production(
            'function_decl : expression OPEN_BRACES expression CLOSE_BRACES OPEN_CURLY_BRACES function_body CLOSE_CURLY_BRACES')
        @self.pg.production(
            'function_decl : expression OPEN_BRACES expression CLOSE_BRACES OPEN_CURLY_BRACES CLOSE_CURLY_BRACES')
        @self.pg.production(
            'function_decl : expression OPEN_BRACES CLOSE_BRACES OPEN_CURLY_BRACES function_body CLOSE_CURLY_BRACES')
        @self.pg.production(
            'function_decl : expression OPEN_BRACES CLOSE_BRACES OPEN_CURLY_BRACES CLOSE_CURLY_BRACES')
        def function_decl(ps: ParserState, p):
            if not isinstance(p[0], VariableDeclaration):
                raise TypeError("Function declaration needs a type and a name")

            decl: VariableDeclaration = p[0]
            params: Node = None
            body: FunctionBody = None

            if isinstance(p[2], Node):
                params = p[2]

            if isinstance(p[5], FunctionBody):
                body = p[5]
            elif isinstance(p[4], FunctionBody):
                body = p[4]

            return FunctionDeclaration(ps, decl.type, decl.name, params, False, body)

        @self.pg.production('function_body : statement')
        @self.pg.production('function_body : function_body statement')
        def function_body(ps: ParserState, p) -> FunctionBody:
            body: FunctionBody

            if len(p) == 2:
                body = p[0]
                body.add_statement(p[1])
            else:
                body = FunctionBody(ps)
                body.add_statement(p[0])

            return body

        @self.pg.production('statement : expression SEMI_COLON')
        def statement(ps: ParserState, p) -> Statement:
            return Statement(ps, p[0])

        @self.pg.production('expression : PARAMS expression')
        def function_params(ps: ParserState, p) -> Node:
            if isinstance(p[1], VariableDeclaration):
                p[1].name += "..."
                return p[1]
            else:
                raise TypeError("params can only be used with function parameter declarations")

        @self.pg.production('expression : IDENTIFIER OPEN_BRACES expression CLOSE_BRACES')
        def function_call(ps: ParserState, p) -> FunctionCall:
            return FunctionCall(ps, p[0].getstr(), p[2])

        @self.pg.production('expression : expression COMMA expression')
        def expression_bag(ps: ParserState, p):
            bag = None

            if isinstance(p[0], ExpressionBag):
                bag = p[0]
            else:
                bag = ExpressionBag(ps)
                bag.expressions.append(p[0])

            bag.expressions.append(p[2])

            return bag

        @self.pg.production('expression : IDENTIFIER IDENTIFIER')
        def variable_decl(ps: ParserState, p):
            return VariableDeclaration(ps, p[0].getstr(), p[1].getstr())

        @self.pg.production('expression : STRING_LIT')
        def string_literal(ps: ParserState, p) -> StringLiteral:
            return StringLiteral(ps, p[0].getstr().replace("\"", ""))

        @self.pg.production('expression : expression SUM expression')
        @self.pg.production('expression : expression SUB expression')
        @self.pg.production('expression : expression MUL expression')
        @self.pg.production('expression : expression DIV expression')
        def expression(ps: ParserState, p) -> BinaryOP:
            left = p[0]
            right = p[2]
            op: Token = p[1]

            if op.gettokentype() == 'SUM':
                return Sum(ps, left, right)
            elif op.gettokentype() == 'SUB':
                return Sub(ps, left, right)
            elif op.gettokentype() == 'MUL':
                return Mul(ps, left, right)
            elif op.gettokentype() == 'DIV':
                return Div(ps, left, right)
            else:
                raise AssertionError('Oops, this should not be possible!')

        @self.pg.production('expression : NUMBER')
        def number(ps: ParserState, p: List[Token]) -> Number:
            return Number(ps, p[0].getstr())

        @self.pg.error
        def error_handler(ps: ParserState, token: Token):
            log_fail(
                f"Unexpected '{token.getstr()}' at {ps.filename}[{token.getsourcepos().lineno}:{token.getsourcepos().colno}]")
            sys.exit(1)

    def get_parser(self) -> LRParser:
        lr_parser: LRParser = self.pg.build()
        lr_table: LRTable = lr_parser.lr_table

        if lr_table.rr_conflicts:
            for conflict in lr_table.rr_conflicts:
                log_warn(f"reduce / reduce conflict for {conflict[1]} in state {conflict[0]} resolved as {conflict[2]}")

        if lr_table.sr_conflicts:
            for conflict in lr_table.sr_conflicts:
                log_warn(f"shift / reduce conflict for {conflict[1]} in state {conflict[0]} resolved as {conflict[2]}")

        return lr_parser
