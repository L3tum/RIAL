from llvmlite import ir

from rial.ASTVisitor import ASTVisitor
from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import null
from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.name_mangler import mangle_global_name
from rial.concept.parser import Tree, Discard
from rial.metadata.RIALFunction import RIALFunction
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
        rial_type = None

        if isinstance(value, RIALVariable):
            if value.global_variable and value.backing_value.global_constant:
                glob = self.llvmgen.gen_global(variable_name, value.backing_value.initializer, value.raw_llvm_type,
                                               access_modifier, access_modifier.get_linkage(),
                                               value.backing_value.global_constant)
            else:
                with self.llvmgen.create_in_global_ctor():
                    glob = self.llvmgen.declare_non_constant_global_variable(variable_name, value.raw_backing_value,
                                                                             access_modifier,
                                                                             access_modifier.get_linkage())

            rial_type = value.rial_type
        elif isinstance(value, RIALFunction):
            glob = self.llvmgen.gen_global(variable_name, ir.PointerType(value), value.function_type, access_modifier,
                                           access_modifier.get_linkage(), False)
            rial_type = str(value.function_type).replace("i8*", "CString")
        else:
            with self.llvmgen.create_in_global_ctor():
                value: RIALVariable = self.ast_visitor.visit(value)

                if isinstance(value, RIALFunction):
                    value: RIALFunction
                    glob = self.llvmgen.gen_global(variable_name, ir.PointerType(value), value.function_type,
                                                   access_modifier,
                                                   access_modifier.get_linkage(), False)
                    rial_type = str(value.function_type).replace("i8*", "CString")
                else:
                    glob = self.llvmgen.gen_global(variable_name, null(value.raw_llvm_type), value.raw_llvm_type,
                                                   access_modifier, access_modifier.get_linkage(), not value.is_pointer)
                    self.llvmgen.builder.store(value.raw_backing_value, glob)
                    rial_type = value.rial_type

        raise Discard()

        # return RIALVariable(variable_name, rial_type, glob, access_modifier)
