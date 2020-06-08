import re
from typing import Optional, List

from llvmlite import ir

from rial.ir.LLVMBlock import LLVMBlock, create_llvm_block
from rial.ir.LLVMIRInstruction import LLVMIRInstruction
from rial.ir.RIALFunction import RIALFunction
from rial.ir.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.ir.RIALVariable import RIALVariable
from rial.transformer.builtin_type_to_llvm_mapper import map_llvm_to_type, is_builtin_type, Int32


class IRBuilder(ir.IRBuilder):
    def create_block(self, block_name: str, parent: Optional[LLVMBlock] = None,
                     sibling: Optional[LLVMBlock] = None) -> \
            Optional[LLVMBlock]:
        block = self.append_basic_block(block_name)
        llvmblock = create_llvm_block(block, parent, sibling)

        return llvmblock

    def create_conditional_jump(self, condition: ir.Value, true_block: LLVMBlock, false_block: LLVMBlock, weights=None):
        if weights is None:
            weights = [50, 50]
        branch = self.cbranch(condition, true_block.block, false_block.block)
        branch.set_weights(weights)

    def create_jump(self, block: LLVMBlock):
        self.branch(block.block)

    def enter_block(self, block: LLVMBlock):
        self.module.current_block = block
        self.position_at_start(block.block)

    def enter_block_end(self, llvmblock: LLVMBlock):
        self.module.current_block = llvmblock
        self.position_at_end(self.module.current_block.block)

    def gen_no_op(self):
        from rial.compilation_manager import CompilationManager
        mod = CompilationManager.modules['rial:builtin:settings']
        glob = mod.get_global_safe("nop_function")
        self.gen_function_call([glob], [])

    def gen_function_call(self, candidates: List, arguments: List[RIALVariable], implicit_parameter=None):
        if len(candidates) > 1:
            from rial.ir.RIALModule import RIALModule
            for duplicate in candidates:
                if isinstance(duplicate, RIALVariable):
                    # Check if wrong module
                    if implicit_parameter is not None and isinstance(implicit_parameter, RIALModule):
                        if duplicate.is_global and duplicate.value.parent.name != implicit_parameter.name:
                            candidates.remove(duplicate)
                            continue
                    # Check if function
                    if not isinstance(duplicate.llvm_type, ir.FunctionType):
                        candidates.remove(duplicate)
                        continue
                elif isinstance(duplicate, RIALIdentifiedStructType):
                    # Check if wrong module
                    if implicit_parameter is not None and isinstance(implicit_parameter, RIALModule):
                        if duplicate.module_name != implicit_parameter.name:
                            candidates.remove(duplicate)
                            continue
                elif isinstance(duplicate, RIALFunction):
                    # Check if wrong module
                    if implicit_parameter is not None and isinstance(implicit_parameter, RIALModule):
                        if duplicate.module.name != implicit_parameter.name:
                            candidates.remove(duplicate)
                            continue
                else:
                    candidates.remove(duplicate)
                    continue

            if len(candidates) > 1:
                for duplicate in candidates:
                    if isinstance(duplicate, RIALFunction):
                        # Check arguments
                        for i, rial_arg in enumerate(duplicate.definition.rial_args):
                            if rial_arg.rial_type != arguments[i].rial_type:
                                candidates.remove(duplicate)
                                break
                    elif isinstance(duplicate, RIALVariable):
                        # Check arguments against function_type parsed to rial_type
                        for i, arg in duplicate.llvm_type.args:
                            if arguments[i].rial_type != map_llvm_to_type(arg.type):
                                candidates.remove(duplicate)
                                break

            if len(candidates) == 1:
                func = candidates[0]
            else:
                raise KeyError(candidates)
        elif len(candidates) == 0:
            raise KeyError(candidates)
        else:
            func = candidates[0]

        if isinstance(func, RIALFunction):
            args = list()
            for arg in arguments:
                # Builtins can be passed but need to be loaded
                if is_builtin_type(arg.rial_type):
                    args.append(arg.get_loaded_if_variable(self.module))

                # Pointer to first element for still normal arrays
                elif re.match(r".+\[[0-9]+\]$", arg.rial_type) is not None:
                    args.append(self.gep(arg.value, [Int32(0), Int32(0)]))

                else:
                    args.append(arg.value)

            # Check if it exists in the current module
            if self.module.get_global_safe(func.name) is None:
                func = self.module.declare_function(func.name, func.canonical_name, func.function_type, func.linkage,
                                                    func.calling_convention, func.definition)

            call_instr = self.call(func, args)

            return RIALVariable(f"call_{func.name}", func.definition.rial_return_type,
                                self.module.get_definition(func.definition.rial_return_type.split('.')),
                                call_instr)
        elif isinstance(func, RIALIdentifiedStructType):
            from rial.ir.RIALModule import RIALModule
            mod: RIALModule = self.module
            funcs = mod.get_functions_by_canonical_name(f"{func.name}_constructor")
            allocad = self.alloca(func)
            variable = RIALVariable(f"{func.name}_allocad", func.name, func, allocad)
            arguments.insert(0, variable)

            # Only if we found at least one constructor. Some structs may not need constructors.
            if len(funcs) > 0:
                self.gen_function_call(funcs, arguments)
            elif len(arguments) > 1:
                raise KeyError(func.name, "constructor")

            return variable

        return None

    def ir(self, ty: ir.Type, llvm_ir: str):
        instr = LLVMIRInstruction(ty, llvm_ir)
        self._insert(instr)

        return instr
