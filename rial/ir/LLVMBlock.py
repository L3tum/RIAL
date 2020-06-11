from typing import Dict, Optional, Any

from llvmlite.ir import Block

from rial.ir.RIALVariable import RIALVariable


class LLVMBlock(Block):
    named_values: Dict[str, RIALVariable]
    llvmblock_parent: Any
    llvmblock_sibling: Any

    def __init__(self, parent, name):
        super().__init__(parent, name)
        self.named_values = dict()
        self.llvmblock_parent = None
        self.llvmblock_sibling = None

    def get_named_value(self, name: str) -> Optional[RIALVariable]:
        current = self
        while True:
            if name in current.named_values:
                return current.named_values[name]
            if current.llvmblock_sibling is not None:
                current = current.llvmblock_sibling
            elif current.llvmblock_parent is not None:
                current = current.llvmblock_parent
            else:
                return None

    def get_block_of_named_value(self, name: str) -> Optional:
        current = self
        while True:
            if name in current.named_values:
                return current
            if current.llvmblock_sibling is not None:
                current = current.llvmblock_sibling
            elif current.llvmblock_parent is not None:
                current = current.llvmblock_parent
            else:
                return None

    def add_named_value(self, name: str, value: RIALVariable):
        self.named_values[name] = value
