import sys

from lark import Transformer, Discard, v_args
from lark.tree import Meta
from llvmlite import ir
from llvmlite.ir import Module, Function, IRBuilder

from rial.ParserState import ParserState
from rial.log import log_fail


class FunctionBodyTransformer(Transformer):
    ps: ParserState
    builder: IRBuilder
    function: Function
    module: Module
    args: list

    def __init__(self, ps: ParserState, module: Module, function: Function, builder: IRBuilder):
        super().__init__()
        self.ps = ps
        self.module = module
        self.function = function
        self.builder = builder
        self.args = list()

    def string(self, nodes):
        value = nodes[0].value.strip("\"")
        name = ".const.string.%s" % value
        value = eval("'{}'".format(value))
        glob = None

        if any(global_variable == name for global_variable in self.ps.global_variables.keys()):
            glob = self.ps.global_variables.get(name)
        else:
            arr = bytearray(value.encode("utf-8") + b"\x00")
            const_char_arr = ir.Constant(ir.ArrayType(ir.IntType(8), len(arr)), arr)
            glob = ir.GlobalVariable(self.module, const_char_arr.type, name=name)
            glob.linkage = 'internal'
            glob.global_constant = True
            glob.initializer = const_char_arr
            self.ps.global_variables[name] = glob

        return self.builder.bitcast(glob, ir.IntType(8).as_pointer())

    def number(self, nodes):
        return ir.Constant(ir.IntType(32), int(nodes[0].value))

    def addition(self, nodes):
        left = nodes[0]
        right = nodes[1]

        return self.builder.add(left, right)

    def subtraction(self, nodes):
        return self.builder.sub(nodes[0], nodes[1])

    def multiplication(self, nodes):
        return self.builder.mul(nodes[0], nodes[1])

    def division(self, nodes):
        return self.builder.sdiv(nodes[0], nodes[1])

    def expression(self, nodes):
        pass

    def function_call(self, nodes):
        function_name = nodes[0].value
        func = next((func for func in self.module.functions if func.name == function_name), None)

        i = 1
        arguments: list = list()
        while i < len(nodes):
            if nodes[i] is None:
                continue

            arguments.append(nodes[i])
            i += 1

        try:
            self.builder.call(func, arguments)
        except IndexError:
            log_fail("Missing argument in function call")
