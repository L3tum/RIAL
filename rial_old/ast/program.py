from typing import List

from rial_old.ast.function_declaration import FunctionDeclaration
from rial_old.ast.node import Node


class Program(Node):
    functions: List[FunctionDeclaration] = list()

    def eval(self):
        for function in self.functions:
            function.eval()
