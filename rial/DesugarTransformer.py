from typing import List

from rial.concept.parser import Tree, Transformer_InPlaceRecursive, Token
from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALFunctionDeclarationModifier import RIALFunctionDeclarationModifier


class DesugarTransformer(Transformer_InPlaceRecursive):
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

        return tree

    def modifier(self, nodes: List):
        access_modifier = RIALAccessModifier.INTERNAL

        for node in nodes:
            if node.type == "ACCESS_MODIFIER":
                access_modifier = RIALAccessModifier[node.value.upper()]

        return RIALFunctionDeclarationModifier(access_modifier=access_modifier)
