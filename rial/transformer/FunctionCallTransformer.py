from typing import List

from rial.concept.parser import Tree
from rial.ir.RIALVariable import RIALVariable
from rial.transformer.BaseTransformer import BaseTransformer


class FunctionCallTransformer(BaseTransformer):
    def function_args(self, tree: Tree):
        arguments = list(map(self.transform_helper, tree.children))

        return arguments

    def function_call(self, tree: Tree):
        nodes = tree.children
        arguments: List[RIALVariable] = self.transform_helper(nodes[1])

        assert isinstance(nodes[0], List)
        func = self.module.get_definition(nodes[0])
        duplicates = set()

        if len(nodes[0]) > 1:
            implicit_parameter = self.module.get_definition(nodes[0][0:-1])

            if implicit_parameter is not None:
                if isinstance(implicit_parameter, RIALVariable):
                    arguments.insert(0, implicit_parameter)
        else:
            implicit_parameter = None

        # Check for canonical names
        duplicates.update(self.module.get_functions_by_canonical_name(nodes[0][-1]))

        # Check for mangled name
        duplicates.add(self.module.get_definition([*(len(nodes[0]) > 1 and nodes[0][0:-1] or []),
                                                   self.module.get_unique_function_name(nodes[0][-1],
                                                                                        [arg.rial_type for arg in
                                                                                         arguments])]))

        if func is not None and func not in duplicates:
            duplicates.add(func)

        if len(duplicates) == 0:
            raise KeyError(nodes[0])

        return self.module.builder.gen_function_call(list(duplicates), arguments, implicit_parameter)
