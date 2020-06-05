from rial.concept.parser import Tree
from rial.stages.post_parsing.PostParsingInterface import PostParsingInterface


class InfiniteLoopDetector(PostParsingInterface):
    def execute(self, ast: Tree):
        while ast is not None:
            self.visit_tree(ast)
            ast = None

    def visit_tree(self, ast: Tree):
       pass