from llvmlite import ir

from rial.concept.parser import Tree
from rial.ir.LLVMUIntType import LLVMUIntType
from rial.ir.RIALVariable import RIALVariable
from rial.transformer.BaseTransformer import BaseTransformer
from rial.transformer.builtin_type_to_llvm_mapper import is_builtin_type


class StandardOperationsTransformer(BaseTransformer):
    def equal(self, tree: Tree):
        nodes = tree.children
        left: RIALVariable = self.transform_helper(nodes[0])
        comparison = nodes[1].value
        right: RIALVariable = self.transform_helper(nodes[2])

        assert isinstance(left, RIALVariable)
        assert isinstance(right, RIALVariable)
        assert isinstance(comparison, str)

        # If both are pointers to arbitrary struct then we need to compare the pointers and not what they contain.
        # At least until we got a Equals method or something to overwrite
        if is_builtin_type(left.rial_type) and left.is_variable:
            left_val = self.module.builder.load(left.value)
        else:
            left_val = left.value

        if is_builtin_type(right.rial_type) and right.is_variable:
            right_val = self.module.builder.load(right.value)
        else:
            right_val = right.value

        # Unsigned and pointers
        if isinstance(left.llvm_type, LLVMUIntType) or (not is_builtin_type(left.rial_type) and left.is_variable):
            result = self.module.builder.icmp_unsigned(comparison, left_val, right_val)
        # Signed
        elif isinstance(left.llvm_type, ir.IntType):
            result = self.module.builder.icmp_signed(comparison, left_val, right_val)
        # Floating
        elif isinstance(left.llvm_type, ir._BaseFloatType):
            result = self.module.builder.fcmp_ordered(comparison, left_val, right_val)
        else:
            raise TypeError(left, right)

        assert isinstance(result, ir.instructions.CompareInstr)

        return RIALVariable(comparison, "Int1", ir.IntType(1), result)

    def math(self, tree: Tree):
        nodes = tree.children
        left: RIALVariable = self.transform_helper(nodes[0])
        op = nodes[1].type
        right: RIALVariable = self.transform_helper(nodes[2])

        assert isinstance(left, RIALVariable)
        assert isinstance(right, RIALVariable)

        if left.rial_type != right.rial_type:
            raise TypeError(left, op, right)

        result = None
        left_val = left.get_loaded_if_variable(self.module)
        right_val = right.get_loaded_if_variable(self.module)

        if op == "PLUS":
            if isinstance(left.llvm_type, ir.IntType):
                result = self.module.builder.add(left_val, right_val)
            elif isinstance(left.llvm_type, ir._BaseFloatType):
                result = self.module.builder.fadd(left_val, right_val)
        elif op == "MINUS":
            if isinstance(left.llvm_type, ir.IntType):
                result = self.module.builder.sub(left_val, right_val)
            elif isinstance(left.llvm_type, ir._BaseFloatType):
                result = self.module.builder.fsub(left_val, right_val)
        elif op == "MUL":
            if isinstance(left.llvm_type, ir.IntType):
                result = self.module.builder.mul(left_val, right_val)
            elif isinstance(left.llvm_type, ir._BaseFloatType):
                result = self.module.builder.fmul(left_val, right_val)
        elif op == "DIV":
            if isinstance(left.llvm_type, LLVMUIntType):
                result = self.module.builder.udiv(left_val, right_val)
            elif isinstance(left.llvm_type, ir.IntType):
                result = self.module.builder.sdiv(left_val, right_val)
            elif isinstance(left.llvm_type, ir._BaseFloatType):
                result = self.module.builder.fdiv(left_val, right_val)
        elif op == "REM":
            if isinstance(left.llvm_type, LLVMUIntType):
                result = self.module.builder.urem(left_val, right_val)
            elif isinstance(left.llvm_type, ir.IntType):
                result = self.module.builder.srem(left_val, right_val)
            elif isinstance(left.llvm_type, ir._BaseFloatType):
                result = self.module.builder.frem(left_val, right_val)

        if result is None:
            raise TypeError(left, op, right)

        return RIALVariable(f"tmp_{op}", left.rial_type, left.llvm_type, result)
