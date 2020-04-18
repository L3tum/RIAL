from rial.concept.parser import Tree, Interpreter, Discard


class TransformerInterpreter(Interpreter):
    """Top-down visitor, recursive

    Visits the tree, starting with the root and finally the leaves (top-down)
    Calls its methods (provided by user via inheritance) according to tree.data

    Unlike Transformer and Visitor, the Interpreter doesn't automatically visit its sub-branches.
    The user has to explicitly call visit_children, or use the @visit_children_decor
    """

    def visit_children(self, tree) -> Tree:
        children = list()

        for child in tree.children:
            if isinstance(child, Tree):
                try:
                    ret = self.visit(child)
                    children.append(ret)
                except Discard:
                    pass
            else:
                children.append(child)

        tree.children = children

        return tree
