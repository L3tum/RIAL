from rial.ASTVisitor import ASTVisitor
from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import null
from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.name_mangler import mangle_global_name
from rial.concept.parser import Discard, Tree
from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


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
        value = body[2]

        with self.llvmgen.create_in_global_ctor():
            value: RIALVariable = self.ast_visitor.transform_helper(value)
            glob = self.llvmgen.gen_global_new(variable_name, value, null(value.llvm_type), access_modifier,
                                               access_modifier.get_linkage(), False)
            self.llvmgen.builder.store(value.value_for_assignment, glob.backing_value)

        raise Discard()
