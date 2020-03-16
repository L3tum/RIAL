from typing import Optional

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

    def __init__(self, opt_level: int):
        self.opt_level = opt_level

        self.binding = binding
        self.binding.initialize()
        self.binding.initialize_native_target()
        self.binding.initialize_native_asmprinter()

        self._create_execution_engine()
        self._create_optimizations()

    def __del__(self):
        self.pm_manager.close()
        self.pm_module.close()

    def _create_optimizations(self):
        self.pm_manager = self.binding.create_pass_manager_builder()
        self.pm_manager.opt_level = self.opt_level
        self.pm_module = self.binding.create_module_pass_manager()

        if self.opt_level > 0:
            self.pm_module.add_type_based_alias_analysis_pass()
            self.pm_module.add_sccp_pass()
            self.pm_module.add_instruction_combining_pass()
            self.pm_module.add_constant_merge_pass()
            self.pm_module.add_global_optimizer_pass()
            self.pm_module.add_cfg_simplification_pass()
            self.pm_module.add_function_inlining_pass(70)
            self.pm_module.add_gvn_pass()
            self.pm_module.add_dead_arg_elimination_pass()
            self.pm_module.add_dead_code_elimination_pass()
            self.pm_module.add_global_dce_pass()
        self.pm_manager.populate(self.pm_module)
        self.target_machine.add_analysis_passes(self.pm_module)

    def _create_execution_engine(self):
        """
        Create an ExecutionEngine suitable for JIT code generation on
        the host CPU.  The engine is reusable for an arbitrary number of
        modules.
        """
        target = self.binding.Target.from_default_triple()
        self.target_machine = target.create_target_machine()
        self.target_machine.set_asm_verbosity(True)

        backing_mod = binding.parse_assembly("")
        engine = binding.create_mcjit_compiler(backing_mod, self.target_machine)
        self.engine = engine
        self.binding.check_jit_execution()

    def _optimize_module(self, module: ModuleRef):
        self.pm_module.run(module)

    def get_module(self, name: str) -> Module:
        module = ir.Module(name=name)
        module.triple = self.binding.get_default_triple()

        return module

    def compile_ir(self, module: Module) -> ModuleRef:
        llvm_ir = str(module)
        mod = self.binding.parse_assembly(llvm_ir)
        mod.verify()

        self._optimize_module(mod)

        self.engine.add_module(mod)
        self.engine.finalize_object()
        self.engine.run_static_constructors()

        return mod

    def save_ir(self, dest: str, module: Module):
        with open(dest, "w") as file:
            file.write(str(module))

    def save_object(self, dest: str, module: ModuleRef):
        with open(dest, "wb") as file:
            file.write(self.target_machine.emit_object(module))

    def save_assembly(self, dest: str, module: ModuleRef):
        with open(dest, "w") as file:
            file.write(self.target_machine.emit_assembly(module))
