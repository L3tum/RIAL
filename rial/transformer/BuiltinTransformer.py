from typing import Optional

from llvmlite import ir

from rial.compilation_manager import CompilationManager
from rial.concept.parser import Tree
from rial.ir.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.ir.RIALVariable import RIALVariable
from rial.transformer.BaseTransformer import BaseTransformer
from rial.transformer.builtin_type_to_llvm_mapper import map_llvm_to_type, Int32


class BuiltinTransformer(BaseTransformer):
    def sizeof(self, tree: Tree):
        nodes = tree.children
        variable: Optional[RIALVariable] = self.transform_helper(nodes[0])

        assert variable is None or isinstance(variable, RIALVariable) or isinstance(variable, ir.Type)

        # "Variable" is actually a type name that we need to extract and then get the size of
        if variable is None:
            ty = self.module.get_definition([node.value for node in nodes[0].children])

            if ty is None:
                raise TypeError(nodes)

            if isinstance(ty, RIALIdentifiedStructType):
                name = ty.name
            else:
                name = map_llvm_to_type(ty)

            size = Int32(CompilationManager.codegen.get_size(ty))

            return RIALVariable(f"sizeof_{name}", "Int32", Int32, size)
        elif isinstance(variable, ir.Type):
            size = Int32(CompilationManager.codegen.get_size(variable))

            return RIALVariable(f"sizeof_{variable}", "Int32", Int32, size)
        elif isinstance(variable.llvm_type, ir.ArrayType) and not isinstance(variable.value, ir.GEPInstr):
            ty: ir.ArrayType = variable.llvm_type

            if isinstance(ty.count, int):
                size = CompilationManager.codegen.get_size(ty.element) * ty.count
                size = Int32(size)
            elif isinstance(ty.count, ir.Constant):
                size = CompilationManager.codegen.get_size(ty.element) * ty.count.constant
                size = Int32(size)
            else:
                size = CompilationManager.codegen.get_size(ty.element)
                size = self.module.builder.mul(Int32(size), self.module.builder.load(ty.count))

            return RIALVariable(f"sizeof_{ty.element}[{ty.count}]", "Int32", Int32, size)
        # If an array wasn't caught in the previous elif, then it doesn't have a set length and needs to be sized this way.
        elif isinstance(variable.value, ir.GEPInstr) or variable.rial_type.endswith("]"):
            # This is worst case and practically only reserved for GEPs
            # This is worst case as it cannot be optimized away.
            base = self.module.builder.ptrtoint(
                self.module.builder.gep(variable.value, [Int32(0)]), Int32)
            val = self.module.builder.ptrtoint(
                self.module.builder.gep(variable.value, [Int32(1)]), Int32)
            size = self.module.builder.sub(val, base)

            return RIALVariable("sizeof_unknown", "Int32", Int32, size)
        else:
            size = Int32(CompilationManager.codegen.get_size(variable.llvm_type))

            return RIALVariable(f"sizeof_{variable.rial_type}", "Int32", Int32, size)

    def unsafe_block(self, tree: Tree):
        nodes = tree.children
        self.module.currently_unsafe = True
        for node in nodes[1:]:
            self.transform_helper(node)
