from llvmlite.ir import Module


class PostIRGenerationInterface:
    def execute(self, module: Module):
        pass
