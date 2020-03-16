import sys
from typing import Tuple, List, Optional

from lark import Transformer, Token, Tree
from llvmlite import ir
from llvmlite.ir import Module, Argument, Function, IRBuilder

from rial.FunctionBodyTransformer import FunctionBodyTransformer
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import map_type_to_llvm
from rial.log import log_fail


class LLVMTransformer(Transformer):
    module: Module
    ps: ParserState

    def init(self, module: Module):
        self.module = module
        self.ps = ParserState()

    def function_decl(self, nodes):
        if nodes[0].type == "EXTERNAL":
            return_type = nodes[1].value
            name = nodes[2].value
            start_args = 3
        else:
            return_type = nodes[0].value
            name = nodes[1].value
            start_args = 2

        args: List[Tuple[str, str]] = list()

        i = start_args
        var_args = False
        has_body = False

        while i < len(nodes):
            if not isinstance(nodes[i], Token):
                has_body = True
                break
            if var_args is True:
                log_fail("PARAMS must be last in arguments")
                break
            if nodes[i].type == "PARAMS":
                var_args = True
                i += 1
            if nodes[i].type == "IDENTIFIER":
                arg_type = nodes[i].value
                i += 1
                arg_name = nodes[i].value

                if var_args:
                    arg_name += "..."

                args.append((arg_type, arg_name))
                i += 1
            else:
                break

        llvm_args = [map_type_to_llvm(arg[0]) for arg in args if not arg[1].endswith("...")]

        llvm_return_type = map_type_to_llvm(return_type)
        func_type = ir.FunctionType(llvm_return_type, tuple(llvm_args), var_arg=var_args)
        func = ir.Function(self.module, func_type, name=name)

        for i, arg in enumerate(func.args):
            arg.name = args[i][1]

        if has_body and nodes[0].type == "EXTERNAL":
            log_fail("External functions cannot have a body!")
            return

        if has_body:
            block = func.append_basic_block("entry")
            builder = ir.IRBuilder(block)
            transformer = FunctionBodyTransformer(self.ps, self.module, func, builder)
            while i < len(nodes):
                transformer.transform(nodes[i])
                i += 1
            builder.ret_void()
