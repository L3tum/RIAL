from typing import List, Tuple

from llvmlite import ir
from llvmlite.ir import Block, Type, Argument

from rial_old.ast.expression_bag import ExpressionBag
from rial_old.ast.function_body import FunctionBody
from rial_old.ast.node import Node
from rial_old.ast.variable_declaration import VariableDeclaration
from rial_old.builtin_type_to_llvm_mapper import map_type_to_llvm
from rial_old.parser_state import ParserState


class FunctionDeclaration(Node):
    external: bool
    function_name: str
    return_type: str
    args: Node
    body: FunctionBody

    def __init__(self, ps: ParserState, return_type: str, function_name: str, args: Node, external: bool,
                 body: FunctionBody = None):
        super().__init__(ps)
        self.return_type = return_type
        self.function_name = function_name
        self.args = args
        self.external = external
        self.body = body

    def eval(self):
        if any(function.name == self.function_name for function in self.ps.module.functions):
            raise NameError(f"Function with name {self.function_name} already declared!")

        llvm_return_type = map_type_to_llvm(self.return_type)

        if llvm_return_type is None:
            raise TypeError(f"Type {self.return_type} cannot be mapped to LLVM!")

        llvm_args, arg_names, var_args = self._eval_args()

        func_type = ir.FunctionType(llvm_return_type, tuple(llvm_args), var_arg=var_args)
        func = ir.Function(self.ps.module, func_type, name=self.function_name)

        # Set the names for the arguments
        for i, arg in enumerate(func.args):
            arg: Argument
            arg.name = arg_names[i]

        if self.external:
            return

        if self.body is not None:
            block: Block = func.append_basic_block(name='entry')
            self.ps.current_function = func
            self.ps.builder = ir.IRBuilder(block)
            self.body.eval()
            self.ps.builder.ret_void()
            self.ps.current_function = None

    def _eval_args(self) -> Tuple[List, List[str], bool]:
        llvm_args: List = list()
        arg_names: List[str] = list()
        var_args: bool = False

        if self.args is None:
            return llvm_args, arg_names, var_args

        if isinstance(self.args, VariableDeclaration):
            if self.args.name.endswith("..."):
                var_args = True
            else:
                llvm_args.append(self._get_llvm_type(self.args.type))
                arg_names.append(self.args.name)
        else:
            if isinstance(self.args, ExpressionBag):
                for expression in self.args.expressions:
                    if isinstance(expression, VariableDeclaration):
                        if expression.name.endswith("..."):
                            var_args = True
                        else:
                            if var_args:
                                raise TypeError("Params parameter MUST be last in the parameter list")
                            llvm_args.append(self._get_llvm_type(expression.type))
                            arg_names.append(expression.name)
                    else:
                        raise TypeError("Only parameter declarations are allowed as function parameters")
            else:
                raise TypeError("Unknown parameter type encountered")

        return llvm_args, arg_names, var_args

    def _get_llvm_type(self, rial_type) -> Type:
        llvm_type = map_type_to_llvm(rial_type)

        if llvm_type is None:
            raise TypeError(f"Type {rial_type} cannot be mapped to LLVM!")

        return llvm_type
