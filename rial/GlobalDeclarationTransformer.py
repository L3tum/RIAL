from llvmlite import ir
from llvmlite.ir import FormattedConstant, GlobalVariable

from rial.ASTVisitor import ASTVisitor
from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.name_mangler import mangle_global_name
from rial.concept.parser import Discard, Tree
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class GlobalDeclarationTransformer(TransformerInterpreter):
    ast_visitor: ASTVisitor
    llvmgen: LLVMGen

    def __init__(self):
        super().__init__()
        self.llvmgen = ParserState.llvmgen()
        self.ast_visitor = ASTVisitor()

    def global_variable_decl(self, tree: Tree):
        body = tree.children[1].children
        access_modifier: RIALAccessModifier = tree.children[0].access_modifier
        variable_name = mangle_global_name(ParserState.module().name, body[0].value)
        variable_value = body[2]
        variable_type = hasattr(variable_value, 'type') and variable_value.type or None

        if not isinstance(variable_value, ir.Constant) or isinstance(variable_value, FormattedConstant):
            if isinstance(variable_value, GlobalVariable) and variable_value.global_constant:
                variable_value = variable_value.initializer
                variable_type = variable_value.initializer.type
            else:
                with self.llvmgen.create_in_global_ctor():
                    variable_value = self.ast_visitor.visit(body[2])

                    glob = self.llvmgen.declare_non_constant_global_variable(variable_name, variable_value,
                                                                             access_modifier,
                                                                             "common")
                raise Discard()
                # raise PermissionError("Global variables can only be of constant types right now")

        glob = self.llvmgen.gen_global(variable_name, variable_value, variable_type, access_modifier,
                                       access_modifier.get_linkage(),
                                       False)

        raise Discard()
