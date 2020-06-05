from typing import List, Dict, Union

from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.parser import Tree, Token, Discard
from rial.ir.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.ir.RIALModule import RIALModule
from rial.ir.RIALVariable import RIALVariable
from rial.ir.llvm_helper import create_identified_struct_type
from rial.ir.metadata.metadata_token import MetadataToken
from rial.ir.modifier.DeclarationModifier import DeclarationModifier
from rial.transformer.FunctionDeclarationTransformer import FunctionDeclarationTransformer
from rial.transformer.builtin_type_to_llvm_mapper import map_llvm_to_type
from rial.util.log import log_fail


class StructDeclarationTransformer(TransformerInterpreter):
    fdt: FunctionDeclarationTransformer
    module: RIALModule

    def __init__(self, module: RIALModule):
        super().__init__()
        self.module = module
        self.fdt = FunctionDeclarationTransformer(self.module)

    def struct_body(self, tree: Tree):
        nodes = tree.children
        collected = {'properties': [], 'function_decls': []}

        for node in nodes:
            if isinstance(node, Tree):
                if node.data == "struct_property_declaration":
                    variable = node.children
                    acc_modifier = variable[0].access_modifier
                    llvm_type = self.module.get_definition(variable[1])

                    if isinstance(llvm_type, RIALIdentifiedStructType):
                        rial_type = llvm_type.name
                    else:
                        rial_type = map_llvm_to_type(llvm_type)

                    variable_name = variable[2].value
                    variable_value = None

                    if len(variable) > 3:
                        variable_value = variable[3]
                    collected['properties'].append(
                        RIALVariable(variable_name, rial_type, llvm_type, variable_value, acc_modifier))
                elif node.data == "function_decl" or node.data == "attributed_function_decl":
                    collected['function_decls'].append(node)
        return collected

    def struct_decl(self, tree: Tree):
        nodes: List = tree.children
        access_modifier = nodes[0].access_modifier
        name = nodes[1].value

        if name in self.module.context.identified_types:
            log_fail(f"Struct {name} has been previously declared!")
            raise Discard()

        struct_body: Dict[str, List[Union[RIALVariable, Tree]]] = self.visit(nodes[-1])
        bases: List[List[str]] = list()

        # Find body of struct (variables)
        i = 2
        while i < len(nodes):
            node: Tree = nodes[i]

            if isinstance(node, List):
                bases.append(node)
            else:
                break
            i += 1

        base_llvm_structs = list()

        for base in bases:
            llvm_struct = self.module.get_definition(base)

            if llvm_struct is not None and isinstance(llvm_struct, RIALIdentifiedStructType):
                base_llvm_structs.append(llvm_struct)
            else:
                log_fail(f"Derived from undeclared type {base}")

        # base_constructor = Tree('function_decl',
        #                         [
        #                             DeclarationModifier(access_modifier, False),
        #                             ["void"],
        #                             Token('IDENTIFIER', "constructor"),
        #                             Tree('function_decl_args', [[name], Token('IDENTIFIER', "this")]),
        #                             *[Tree('function_call', [
        #                                 Token('IDENTIFIER', "constructor"),
        #                                 Tree('function_args',
        #                                      [Tree('cast', [Token('IDENTIFIER', base.name),
        #                                                     Tree('var', [Token('IDENTIFIER', "this")])])])])
        #                               for base in base_llvm_structs],
        #                             *[Tree('variable_assignment',
        #                                    [Tree('var', [Token('IDENTIFIER', f"this.{bod.name}")]),
        #                                     Token('ASSIGN', '='),
        #                                     bod.value]) for bod in struct_body['properties']],
        #                             Tree('return', [Token('IDENTIFIER', "void")])
        #                         ]
        #                         )
        # struct_body['function_decls'].insert(0, base_constructor)
        struct = create_identified_struct_type(self.module, name, access_modifier, base_llvm_structs,
                                               struct_body['properties'])
        self.module.current_struct = struct

        declared_functions = list()

        # Create functions
        for function_decl in struct_body['function_decls']:
            metadata_node = self.fdt.visit(function_decl)
            if metadata_node is not None:
                declared_functions.append(metadata_node)
            try:
                nodes.remove(function_decl)
            except ValueError:
                pass

        self.module.current_block = None
        self.module.current_func = None
        self.module.current_struct = None

        node: Token = nodes[1]
        nodes.pop(1)

        node: MetadataToken = MetadataToken(node.type, node.value)
        node.metadata['struct'] = struct
        node.metadata['functions'] = declared_functions

        nodes.insert(0, node)

        return Tree('struct_decl', nodes)
