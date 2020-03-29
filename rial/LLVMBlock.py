from typing import Dict, Optional, Any

from llvmlite.ir import Block, Value


class LLVMBlock:
    block: Block
    named_values: Dict[str, Value]
    parent: Any
    sibling: Any

    def __init__(self, block: Block):
        self.block = block
        self.named_values = dict()

    def get_named_value(self, name: str) -> Optional[Value]:
        current = self
        while True:
            if name in current.named_values:
                return current.named_values[name]
            if current.sibling is not None:
                current = current.sibling
            elif current.parent is not None:
                current = current.parent
            else:
                return None

    def add_named_value(self, name: str, value: Value):
        self.named_values[name] = value


def create_llvm_block(block: Block, parent: Optional[LLVMBlock] = None, sibling: Optional[LLVMBlock] = None):
    llvmblock = LLVMBlock(block)
    llvmblock.parent = parent
    llvmblock.sibling = sibling

    return llvmblock
