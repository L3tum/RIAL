from typing import List

from rial.concept.parser import Tree, Transformer_InPlaceRecursive


class DesugarTransformer(Transformer_InPlaceRecursive):
    def conditional_elif_block(self, nodes: List):
        tree = Tree('conditional_block', [])
        root_tree = tree

        i = 0
        while i < len(nodes):
            # Check if more nodes left and current tree is "full"
            if len(nodes) > i + 1 and len(tree.children) >= 2:
                new_tree = Tree('conditional_block', [nodes[i]])
                tree.children.append(new_tree)
                tree = new_tree
            else:
                tree.children.append(nodes[i])
            i += 1

        return root_tree
