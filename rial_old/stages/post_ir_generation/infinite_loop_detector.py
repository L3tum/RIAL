from llvmlite.ir import Branch, Module

from rial.metadata.RIALFunction import RIALFunction
from rial.stages.post_ir_generation.PostIRGenerationInterface import PostIRGenerationInterface


class InfiniteLoopDetector(PostIRGenerationInterface):
    def execute(self, module: Module):
        for func in module.functions:
            func: RIALFunction

            for block in func.blocks:
                if isinstance(block.terminator, Branch):
                    if block.terminator.operands[0] == block:
                        raise AssertionError("Infinite loop")
