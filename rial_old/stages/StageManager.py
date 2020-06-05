from enum import Enum
from typing import List

from rial.compilation_manager import CompilationManager
from rial.profiling import run_with_profiling, ExecutionStep
from rial.stages.post_ir_generation.PostIRGenerationInterface import PostIRGenerationInterface
from rial.stages.post_ir_generation.infinite_loop_detector import InfiniteLoopDetector

POST_IR_GEN_STAGE: List[PostIRGenerationInterface] = [
    InfiniteLoopDetector()
]


class Stage(Enum):
    POST_IR_GEN = "Post IR Generation Stage"


def execute_post_ir_gen_stage():
    for key, module in CompilationManager.modules.items():
        for executor in POST_IR_GEN_STAGE:
            executor.execute(module)


def execute_stage(stage: Stage):
    with run_with_profiling(stage.name, ExecutionStep.HOOKED_STAGE):
        if stage == Stage.POST_IR_GEN:
            execute_post_ir_gen_stage()
