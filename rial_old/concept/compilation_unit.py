from rial.concept.parser import Tree
from rial.metadata.RIALModule import RIALModule


class CompilationUnit:
    ast: Tree
    module: RIALModule
    last_modified: float

    def __init__(self, module: RIALModule, last_modified: float, ast: Tree):
        self.module = module
        self.last_modified = last_modified
        self.ast = ast
