from threading import Lock

from llvmlite import ir, binding
from llvmlite.binding import ExecutionEngine, ModuleRef, TargetMachine, PassManagerBuilder, ModulePassManager
from llvmlite.ir import Module


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

    def __del__(self):
        self.pm_manager.close()
        self.pm_module.close()

    def _create_execution_engine(self):
        """
        Create an ExecutionEngine suitable for JIT code generation on
        the host CPU.  The engine is reusable for an arbitrary number of
        modules.
        """
        target = self.binding.Target.from_default_triple()
        self.target_machine = target.create_target_machine(
            opt=self.opt_level in ("0", "1", "2", "3") and int(self.opt_level) or 0)
        self.target_machine.set_asm_verbosity(True)

        backing_mod = binding.parse_assembly("")
        engine = binding.create_mcjit_compiler(backing_mod, self.target_machine)
        self.engine = engine
        self.binding.check_jit_execution()

    def _optimize_module(self, module: ModuleRef):
        if self.opt_level > 0:
            pm_manager = self.binding.create_pass_manager_builder()
            pm_manager.loop_vectorize = True
            pm_manager.slp_vectorize = True
            pm_manager.size_level = 0
            pm_manager.opt_level = self.opt_level in ("0", "1", "2", "3") and int(self.opt_level) or 0
            pm_module = self.binding.create_module_pass_manager()
            self.target_machine.add_analysis_passes(pm_module)
            pm_function = self.binding.create_function_pass_manager(module)
            self.target_machine.add_analysis_passes(pm_function)
            pm_manager.populate(pm_function)
            pm_manager.populate(pm_module)

            pm_function.initialize()
            for func in module.functions:
                if not func.is_declaration:
                    pm_function.run(func)
            pm_function.finalize()

            pm_module.run(module)

    def get_module(self, name: str) -> Module:
        module = ir.Module(name=name)
        module.triple = self.binding.get_default_triple()
        module.data_layout = self.target_machine.target_data
        module.add_named_metadata('compiler', ('RIALC',))

        return module

    def compile_ir(self, module: Module) -> ModuleRef:
        with self.lock:
            llvm_ir = str(module)
            mod = self.binding.parse_assembly(llvm_ir)
            mod.verify()

            self._optimize_module(mod)

            self.engine.add_module(mod)
            self.engine.finalize_object()
            self.engine.run_static_constructors()

        return mod

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
