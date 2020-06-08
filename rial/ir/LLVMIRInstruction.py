from llvmlite.ir import Type


class LLVMIRInstruction:
    type: Type
    ir: str

    def __init__(self, ty: Type, ir: str):
        self.ir = ir
        self.type = ty

    def descr(self, buf):
        buf.append(self.ir)

    def get_reference(self):
        buf = []
        self.descr(buf)
        return "".join(buf)

    def __str__(self):
        return "{0}".format(self.get_reference())
