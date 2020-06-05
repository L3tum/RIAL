from typing import List

from llvmlite import ir

from rial.compilation_manager import CompilationManager
from rial.concept.parser import Tree, Transformer_InPlaceRecursive, Token, Discard
from rial.ir.RIALModule import RIALModule
from rial.ir.RIALVariable import RIALVariable
from rial.ir.modifier.AccessModifier import AccessModifier
from rial.ir.modifier.DeclarationModifier import DeclarationModifier
from rial.ir.modifier.VariableMutabilityModifier import VariableMutabilityModifier
from rial.transformer.builtin_type_to_llvm_mapper import NULL, TRUE, FALSE, convert_number_to_constant, map_llvm_to_type
from rial.util.log import log_warn_short
from rial.util.util import good_hash


class DesugarTransformer(Transformer_InPlaceRecursive):
    module: RIALModule

    def __init__(self, module: RIALModule):
        super().__init__()
        self.module = module

    def conditional_block(self, nodes: List):
        tree = Tree('conditional_block', [])
        root_tree = tree

        for node in nodes:
            if isinstance(node, Tree) and node.data == "conditional_elif_block":
                new_tree = Tree('conditional_block', [])
                new_tree.children.extend(node.children)
                tree.children.append(new_tree)
                tree = new_tree
            else:
                tree.children.append(node)

        return root_tree

    def likely_unlikely_modifier(self, nodes: List):
        if len(nodes) == 0:
            return Token('STANDARD_WEIGHT', 50)
        if nodes[0].type == "LIKELY":
            return nodes[0].update(value=100)
        elif nodes[0].type == "UNLIKELY":
            return nodes[0].update(value=10)
        raise KeyError()

    def variable_arithmetic(self, nodes: List):
        tree = Tree('variable_assignment', [])
        tree.children.append(nodes[0])
        tree.children.append(nodes[2])
        math_tree = Tree('math', [])
        math_tree.children.append(nodes[0])
        math_tree.children.append(nodes[1])
        if isinstance(nodes[2], Token) and nodes[2].type == "ASSIGN":
            math_tree.children.append(nodes[3])
        else:
            one_tree = Tree('number', [])
            one_tree.children.append(nodes[2].update('NUMBER', '1'))
            math_tree.children.append(one_tree)
        tree.children.append(math_tree)

        return self.transform(tree)

    def modifier(self, nodes: List):
        access_modifier = AccessModifier.INTERNAL
        unsafe = False

        for node in nodes:
            node: Token
            if node.type == "ACCESS_MODIFIER":
                access_modifier = AccessModifier[node.value.upper()]
            elif node.type == "UNSAFE":
                if unsafe:
                    log_warn_short(f"Multiple unsafe declarations for function at {node.line}")
                unsafe = True

        return DeclarationModifier(access_modifier=access_modifier, unsafe=unsafe)

    def unsafe_top_level_block(self, nodes: List):
        """
        Depends on the modifier parsing function above. If this is somehow executed before that,
        then this function will not break, but will not work.
        :param nodes:
        :return:
        """
        for node in nodes:
            if isinstance(node, Tree):
                if isinstance(node.children[0], DeclarationModifier):
                    node.children[0].unsafe = True

        return Tree('start', nodes)

    def imported(self, nodes):
        mutability = nodes[0]

        if mutability != VariableMutabilityModifier.CONST:
            raise PermissionError("Cannot import modules as anything but const variables")

        var_name = nodes[1].value

        if var_name in self.module.dependencies:
            raise NameError(var_name)

        mod_name = ':'.join([node.value for node in nodes[3:]])
        CompilationManager.request_module(mod_name)
        self.module.dependencies[var_name] = mod_name

        raise Discard()

    def null(self, nodes):
        return RIALVariable("null", "Int8", NULL.type, NULL)

    def true(self, nodes):
        return RIALVariable("true", "Int1", TRUE.type, TRUE)

    def false(self, nodes):
        return RIALVariable("false", "Int1", FALSE.type, FALSE)

    def number(self, nodes: List):
        value: str = nodes[0].value
        number = convert_number_to_constant(value)
        return RIALVariable("number", map_llvm_to_type(number.type), number.type, number)

    def string(self, nodes):
        value = nodes[0].value.strip("\"")
        name = ".const.string.%s" % good_hash(value)

        # Parse escape codes to be correct
        value = eval("'{}'".format(value))
        value = f"{value}\00"
        arr = bytearray(value.encode("utf-8"))
        const_char_arr = ir.Constant(ir.ArrayType(ir.IntType(8), len(arr)), arr)
        glob = self.module.declare_global(name, "Char[]", const_char_arr.type, "private", const_char_arr,
                                          AccessModifier.PRIVATE, True)

        return glob

    def variable_mutability(self, nodes):
        mutability = nodes[0].value

        if mutability == "const":
            return VariableMutabilityModifier.CONST
        elif mutability == "mut":
            return VariableMutabilityModifier.MUT
        elif mutability == "ref":
            return VariableMutabilityModifier.REF

        raise NameError(mutability)

    def chained_identifier(self, nodes):
        return [node.value for node in nodes]
