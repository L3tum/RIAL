from typing import Dict

from llvmlite.ir import Function, IRBuilder, Module


class ParserState(object):
    filename: str
    current_function: Function
    module: Module
    builder: IRBuilder
    global_variables: Dict

    def __init__(self, filename: str, module: Module):
        self.filename = filename
        self.module = module
        self.global_variables = dict()
