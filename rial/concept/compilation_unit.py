from typing import List

from rial.concept.parser import Tree
from rial.metadata.RIALModule import RIALModule


class CompilationUnit:
    ast: Tree
    module: RIALModule
    usings: List[str]
    last_modified: float

    def __init__(self, module: RIALModule, usings: List[str], last_modified: float, ast: Tree):
        self.module = module
        self.usings = usings
        self.last_modified = last_modified
        self.ast = ast
