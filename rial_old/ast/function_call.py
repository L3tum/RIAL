from typing import List

from rial_old.ast.expression_bag import ExpressionBag
from rial_old.ast.node import Node
from rial_old.parser_state import ParserState


class FunctionCall(Node):
    args: Node
    function_name: str

    def __init__(self, ps: ParserState, function_name: str, args: Node):
        super().__init__(ps)
        self.function_name = function_name
        self.args = args

    def eval(self):
        evaled_args: List = list()

        if isinstance(self.args, ExpressionBag):
            for expression in self.args.expressions:
                evaled_args.append(expression.eval())
        else:
            evaled_args.append(self.args.eval())

        func = None

        for function in self.ps.module.functions:
            if function.name == self.function_name:
                func = function
                break

        if func is None:
            raise NameError(self.function_name)

        self.ps.builder.call(func, evaled_args)
