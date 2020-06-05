from rial.concept.parser import Tree, Interpreter, Discard


class TransformerInterpreter(Interpreter):
    """Top-down visitor, recursive

    Visits the tree, starting with the root and finally the leaves (top-down)
    Calls its methods (provided by user via inheritance) according to tree.data

    Unlike Transformer and Visitor, the Interpreter doesn't automatically visit its sub-branches.
    The user has to explicitly call visit_children, or use the @visit_children_decor
    """

    def visit(self, tree):
        f = getattr(self, tree.data)
        wrapper = getattr(f, 'visit_wrapper', None)
        try:
            if wrapper is not None:
                return f.visit_wrapper(f, tree.data, tree.children, tree.meta)
            else:
                return f(tree)
        except Discard:
            pass
        except Exception as e:
            from rial.util.log import log_fail
            log_fail(e)
            from rial.compilation_manager import CompilationManager
            log_fail(
                f"Current Module: {CompilationManager.current_module is not None and CompilationManager.current_module.name or ''}")
            import traceback
            log_fail(traceback.format_exc())

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
