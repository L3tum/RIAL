from typing import List

from rial.FunctionDeclarationTransformer import FunctionDeclarationTransformer
from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.concept.parser import Tree, Token, Discard
from rial.log import log_fail
from rial.rial_types.RIALFunctionDeclarationModifier import RIALFunctionDeclarationModifier
from rial.rial_types.RIALVariable import RIALVariable


class StructDeclarationTransformer(TransformerInterpreter):
    llvmgen: LLVMGen

    def __init__(self):
        super().__init__()
        self.llvmgen = LLVMGen()
        self.fdt = FunctionDeclarationTransformer()

        # This guarantees that variables such as current_struct and the like are also visible in the FDT
        self.fdt.llvmgen = self.llvmgen

    def struct_decl(self, tree: Tree):
        nodes: List = tree.children
        access_modifier = nodes[0].access_modifier
        name = nodes[1].value

        full_name = f"{ParserState.module().name}:{name}"

        if ParserState.search_structs(full_name) is not None:
            log_fail(f"Struct {full_name} has been previously declared!")
            raise Discard()

        body: List[RIALVariable] = list()
        function_decls: List[Tree] = list()
        bases: List[str] = list()

        # Find body of struct (variables)
        i = 2
        while i < len(nodes):
            node: Tree = nodes[i]

            if isinstance(node, Tree) and node.data == "struct_property_declaration":
                variable = node.children
                acc_modifier = variable[0].access_modifier
                rial_type = variable[1].value
                variable_name = variable[2].value
                variable_value = None

                if len(variable) > 3:
                    variable_value = variable[3]

                body.append(
                    RIALVariable(variable_name, ParserState.module().name, rial_type, backing_value=variable_value,
                                 access_modifier=acc_modifier))
            elif isinstance(node, Tree) and node.data == "function_decl":
                function_decls.append(node)
            elif isinstance(node, Token) and node.type == "IDENTIFIER":
                bases.append(node.value)
            i += 1

        base_llvm_structs = list()

        for base in bases:
            llvm_struct = ParserState.find_struct(base)

            if llvm_struct is not None:
                base_llvm_structs.append(llvm_struct)
            else:
                log_fail(f"Derived from undeclared type {base}")

        base_constructor = Tree('function_decl',
                                [
                                    RIALFunctionDeclarationModifier(access_modifier),
                                    Token('IDENTIFIER', "void"),
                                    Token('IDENTIFIER', "constructor"),
                                    *[Tree('function_call', [
                                        Token('IDENTIFIER', mangle_function_name("constructor", [base], base.name)),
                                        Tree('function_args',
                                             [Tree('cast', [Token('IDENTIFIER', base.name),
                                                            Tree('var', [Token('IDENTIFIER', "this")])])])])
                                      for base in base_llvm_structs],
                                    *[Tree('variable_assignment',
                                           [Tree('var', [Token('IDENTIFIER', f"this.{bod.name}")]),
                                            Token('ASSIGN', '='),
                                            bod.backing_value]) for bod in body],
                                    Tree('return', [Token('IDENTIFIER', "void")])
                                ]
                                )
        function_decls.insert(0, base_constructor)

        llvm_struct = self.llvmgen.create_identified_struct(full_name,
                                                            access_modifier.get_linkage(),
                                                            access_modifier,
                                                            base_llvm_structs,
                                                            body)

        declared_functions = list()

        # Create functions
        for function_decl in function_decls:
            metadata_node = self.fdt.visit(function_decl)
            if metadata_node is not None:
                declared_functions.append(metadata_node)
            try:
                nodes.remove(function_decl)
            except ValueError:
                pass

        self.llvmgen.finish_struct()

        node: Token = nodes[1]
        md_node = MetadataToken(node.type, node.value)

        md_node.metadata['struct_name'] = full_name
        md_node.metadata['functions'] = declared_functions
        nodes.remove(node)
        nodes.insert(0, md_node)

        return Tree('struct_decl', nodes)
