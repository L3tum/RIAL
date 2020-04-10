import traceback
from threading import Lock
from typing import Optional

from llvmlite import ir, binding
from llvmlite.binding import ExecutionEngine, ModuleRef, TargetMachine, PassManagerBuilder, ModulePassManager
from llvmlite.ir import Module

from rial.log import log_fail


class CodeGen:
    opt_level: int
    engine: ExecutionEngine
    binding: binding
    target_machine: TargetMachine
    pm_manager: PassManagerBuilder
    pm_module: ModulePassManager
    lock: Lock

    def __init__(self, opt_level: str):
        self.lock = Lock()
        self.opt_level = opt_level in ("0", "1", "2", "3") and int(opt_level) or 0

        self.binding = binding
        self.binding.initialize()
        self.binding.initialize_native_target()
        self.binding.initialize_native_asmprinter()

        self._create_execution_engine()

    def _create_execution_engine(self):
        """
        Create an ExecutionEngine suitable for JIT code generation on
        the host CPU.  The engine is reusable for an arbitrary number of
        modules.
        """
        target = self.binding.Target.from_default_triple()
        self.target_machine = target.create_target_machine(opt=self.opt_level, reloc="pic")
        self.target_machine.set_asm_verbosity(True)

        backing_mod = binding.parse_assembly("")
        engine = binding.create_mcjit_compiler(backing_mod, self.target_machine)
        self.engine = engine
        self.binding.check_jit_execution()

    def _optimize_module(self, module: ModuleRef):
        """
        Currently unused as it produces invalid output.
        Would be great if there'd be any documentation on this....
        :param module:
        :return:
        """
        if self.opt_level > 0:
            pm_manager = self.binding.create_pass_manager_builder()
            pm_manager.loop_vectorize = self.opt_level > 0
            pm_manager.slp_vectorize = self.opt_level > 0
            pm_manager.size_level = 0
            pm_manager.opt_level = self.opt_level
            pm_module = self.binding.create_module_pass_manager()
            pm_function = self.binding.create_function_pass_manager(module)
            pm_manager.populate(pm_function)
            pm_manager.populate(pm_module)

            pm_function.initialize()
            for func in module.functions:
                if not func.is_declaration:
                    pm_function.run(func)
            pm_function.finalize()

            pm_module.run(module)

            pm_module.close()
            pm_manager.close()

    def get_module(self, name: str) -> Module:
        module = ir.Module(name=name)
        module.triple = self.binding.get_default_triple()
        module.data_layout = self.target_machine.target_data
        module.add_named_metadata('compiler', ('RIALC',))

        return module

    def compile_ir(self, module: Module) -> ModuleRef:
        with self.lock:
            llvm_ir = str(module)
            try:
                mod = self.binding.parse_assembly(llvm_ir)
                mod.verify()
            except Exception as e:
                log_fail(llvm_ir)
                raise e

            self._optimize_module(mod)

        return mod

    def generate_final_module(self, mod: ModuleRef):
        self.engine.add_module(mod)
        self.engine.finalize_object()
        self.engine.run_static_constructors()
        self.engine.remove_module(mod)

    def save_ir(self, dest: str, module: ModuleRef):
        with open(dest, "w") as file:
            file.write(str(module))

    def save_object(self, dest: str, module: ModuleRef):
        with open(dest, "wb") as file:
            file.write(self.target_machine.emit_object(module))

    def save_assembly(self, dest: str, module: ModuleRef):
        with open(dest, "w") as file:
            file.write(self.target_machine.emit_assembly(module))

    def save_llvm_bitcode(self, dest: str, module: ModuleRef):
        with open(dest, "wb") as file:
            file.write(module.as_bitcode())
