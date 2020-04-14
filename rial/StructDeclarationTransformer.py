from typing import List

from rial.FunctionDeclarationTransformer import FunctionDeclarationTransformer
from rial.LLVMFunction import LLVMFunction
from rial.ParserState import ParserState
from rial.SingleParserState import SingleParserState
from rial.concept.metadata_token import MetadataToken
from rial.concept.parser import Transformer_InPlaceRecursive, Tree, Token, Discard
from rial.log import log_fail
from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class StructDeclarationTransformer(Transformer_InPlaceRecursive):
    fdt: FunctionDeclarationTransformer
    sps: SingleParserState

    def init(self, sps: SingleParserState, fdt: FunctionDeclarationTransformer):
        self.sps = sps
        self.fdt = fdt

    def struct_decl(self, nodes: List):
        if nodes[0].type == "ACCESS_MODIFIER":
            access_modifier = RIALAccessModifier[nodes[0].value.upper()]
            name = nodes[1].value
            start = 2
        else:
            access_modifier = RIALAccessModifier.PRIVATE
            name = nodes[0].value
            start = 1

        full_name = f"{self.sps.llvmgen.module.name}:{name}"

        if ParserState.search_structs(full_name) is not None:
            log_fail(f"Struct {full_name} has been previously declared!")
            raise Discard()

        body: List[RIALVariable] = list()
        function_decls: List[Tree] = list()

        # Find body of struct (variables)
        i = start
        while i < len(nodes):
            node: Tree = nodes[i]

            if isinstance(node, Tree) and node.data == "struct_property_declaration":
                variable = node.children
                rial_type = variable[0].value
                variable_name = variable[1].value
                llvm_type = self.sps.map_type_to_llvm(rial_type)
                variable_value = None

                if len(variable) > 2:
                    variable_value = variable[2]

                body.append(RIALVariable(variable_name, rial_type, llvm_type, initial_value=variable_value))
            elif isinstance(node, Tree) and node.data == "function_decl":
                function_decls.append(node)
            i += 1

        llvm_struct = self.sps.llvmgen.create_identified_struct(full_name, self.sps.llvmgen.module.name,
                                                                access_modifier.get_linkage(),
                                                                access_modifier,
                                                                body)
        ParserState.structs[full_name] = llvm_struct

        declared_functions = list()

        # Create functions
        for function_decl in function_decls:
            metadata_node = self.fdt.transform(function_decl)
            nodes.remove(function_decl)
            declared_functions.append(metadata_node)

        self.sps.llvmgen.finish_struct()

        node: Token = nodes[0]
        md_node = MetadataToken(node.type, node.value)

        md_node.metadata['struct_name'] = full_name
        md_node.metadata['functions'] = declared_functions
        nodes.remove(node)
        nodes.insert(0, md_node)

        return Tree('struct_decl', nodes)
