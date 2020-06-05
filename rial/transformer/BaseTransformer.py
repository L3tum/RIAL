from typing import List

from rial.concept.combined_transformer import CombinedTransformer
from rial.concept.parser import Tree
from rial.ir.RIALModule import RIALModule


class BaseTransformer:
    combined_transformer: CombinedTransformer
    module: RIALModule

    def __init__(self):
        super().__init__()
        from rial.compilation_manager import CompilationManager
        self.module = CompilationManager.current_module

    def var(self, tree: Tree):
        nodes = tree.children

        # Since var is using the chained_identifier
        assert isinstance(nodes[0], List)

        return self.module.get_definition(nodes[0])

    def transform_helper(self, tree):
        if isinstance(tree, Tree):
            return self.combined_transformer.visit(tree)

        return tree
