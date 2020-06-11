import re
from contextlib import contextmanager
from typing import Dict, Optional, Union, List, Tuple

from llvmlite import ir
from llvmlite.ir import Module, Context, Block, AllocaInstr

from rial.ir.IRBuilder import IRBuilder
from rial.ir.LLVMBlock import LLVMBlock
from rial.ir.RIALFunction import RIALFunction
from rial.ir.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.ir.RIALVariable import RIALVariable
from rial.ir.metadata.FunctionDefinition import FunctionDefinition
from rial.ir.modifier.AccessModifier import AccessModifier
from rial.transformer.builtin_type_to_llvm_mapper import Int32, map_type_to_llvm, map_shortcut_to_type, NULL, \
    map_llvm_to_type


class RIALModule(Module):
    dependencies: Dict[str, str]
    filename: str
    current_block: Optional[LLVMBlock]
    conditional_block: Optional[LLVMBlock]
    end_block: Optional[LLVMBlock]
    current_struct: Optional[RIALIdentifiedStructType]
    current_func: Optional[RIALFunction]
    global_variables: Dict[str, RIALVariable]
    builder: Optional[IRBuilder]
    currently_unsafe: bool

    def __init__(self, name='', context=Context()):
        super().__init__(name, context)
        self.dependencies = dict()
        self.filename = ""
        self.current_block = None
        self.conditional_block = None
        self.end_block = None
        self.current_struct = None
        self.current_func = None
        self.global_variables = dict()
        self.builder = None
        self.currently_unsafe = False

    def get_global_safe(self: Module, name: str) -> Optional[Union[ir.GlobalValue, RIALFunction]]:
        try:
            return self.get_global(name)
        except KeyError:
            return None

    def _get_recursive_definition(self, identifier: str, variable: Optional[
        Union[RIALVariable, RIALFunction, ir.Module, RIALIdentifiedStructType, ir.Type]]) -> Optional[
        Union[RIALVariable, RIALFunction, ir.Module, RIALIdentifiedStructType, ir.Type]]:
        assert isinstance(identifier, str)

        if variable is not None:
            if isinstance(variable, RIALModule):
                return variable.get_definition([identifier])
            elif isinstance(variable, RIALFunction):
                return None
            elif isinstance(variable, RIALIdentifiedStructType):
                return None
            elif isinstance(variable, RIALVariable):
                if not isinstance(variable.llvm_type, RIALIdentifiedStructType):
                    return None

                struct: RIALIdentifiedStructType = variable.llvm_type

                # Check properties
                if identifier in struct.definition.properties:
                    if self.builder is None:
                        return None

                    prop = struct.definition.properties[identifier]
                    return RIALVariable(identifier, prop[1].rial_type, prop[1].llvm_type,
                                        self.builder.gep(variable.value, [Int32(0), Int32(prop[0])]),
                                        prop[1].access_modifier)

                # Check functions
                from rial.compilation_manager import CompilationManager
                mod = struct.module_name == self.name and self or CompilationManager.modules[struct.module_name]
                variable = mod.get_global_safe(identifier)

                if variable is not None:
                    if isinstance(variable, RIALFunction):
                        if len(variable.definition.rial_args) > 0 and variable.definition.rial_args[
                            0].rial_type == struct.name:
                            return variable

            return None

        # Check builtin's first
        identifier = map_shortcut_to_type(identifier)
        variable = map_type_to_llvm(identifier)

        if variable is None:
            # Arrays
            match = re.match(r"^([^\[]+)\[([0-9]+)?\]$", identifier)

            if match is not None:
                ty = match.group(1)
                count = match.group(2)
                definition = self.get_definition([ty])
                if definition is not None:
                    if count is not None:
                        return ir.ArrayType(definition, int(count))
                    else:
                        return definition.as_pointer()

            # Function type
            match = re.match(r"^([^(]+)\(([^,)]+\s*,?\s*)*\)$", identifier)

            if match is not None:
                return_type = ""
                arg_types = list()
                var_args = False
                for i, group in enumerate(match.groups()):
                    if i == 0:
                        return_type = group.strip()
                    elif group == "...":
                        var_args = True
                    elif group is None:
                        break
                    else:
                        arg_types.append(group.strip())

                return ir.FunctionType(self.get_definition([return_type]),
                                       [self.get_definition([arg]) for arg in arg_types],
                                       var_args)

        # Check local variables first
        if variable is None and self.current_block is not None:
            variable = self.current_block.get_named_value(identifier)

        # Check module-local global variables next
        if variable is None:
            variable = identifier in self.global_variables and self.global_variables[identifier] or None

        # Check structs next
        if variable is None:
            variable = identifier in self.get_identified_types() and \
                       self.get_identified_types()[identifier] or None

        # Check functions next
        if variable is None:
            variable = self.get_global_safe(identifier)

        # Check module imports
        if variable is None:
            mod = identifier in self.dependencies and self.dependencies[identifier] or None

            if mod is not None:
                from rial.compilation_manager import CompilationManager
                variable = CompilationManager.modules[mod]

        # Check always imported last
        if variable is None and not self.name.startswith("rial:builtin:"):
            from rial.compilation_manager import CompilationManager
            for always_imported in CompilationManager.always_imported:
                mod = CompilationManager.modules[always_imported]
                variable = mod.get_definition([identifier])

                if variable is not None:
                    break

        return variable

    def get_definition(self, identifiers: List[str]) -> Optional[
        Union[RIALVariable, RIALFunction, ir.Module, RIALIdentifiedStructType, ir.Type]]:
        assert isinstance(identifiers, List)

        variable = None

        for identifier in identifiers:
            assert isinstance(identifier, str)
            variable = self._get_recursive_definition(identifier, variable)

            if variable is None:
                break

        return variable

    def get_functions_by_canonical_name(self, canonical_name: str) -> List[RIALFunction]:
        from rial.compilation_manager import CompilationManager
        funcs = [func for func in self.functions if func.canonical_name == canonical_name]

        for module in self.dependencies.values():
            try:
                mod = CompilationManager.modules[module]
                funcs.extend(mod.get_functions_by_canonical_name(canonical_name))
            except KeyError:
                print(module, CompilationManager.modules.keys())

        return funcs

    def get_llvm_type_from_rial_type(self, rial_type: str):
        assert isinstance(rial_type, str)

        llvm_type = map_type_to_llvm(rial_type)

        if llvm_type is None:
            llvm_type = self.get_definition(rial_type.split('.'))

        return llvm_type

    def get_unique_function_name(self, canonical_name: str, rial_args: List[str]):
        assert isinstance(canonical_name, str)
        assert isinstance(rial_args, List)
        clean_args = list()

        for rial_arg in rial_args:
            if '[' in rial_arg:
                rial_arg = f"{rial_arg.split('[')[0]}[]"
            clean_args.append(rial_arg)

        return f"mangled_{canonical_name}{len(rial_args) > 0 and '.' or ''}{'_'.join(clean_args)}"

    def declare_global(self, name: str, rial_type: str, llvm_type: ir.Type, linkage: str,
                       initializer: Optional[ir.Constant], access_modifier: AccessModifier = AccessModifier.PRIVATE,
                       constant: bool = False):
        if self.get_global_safe(name) is not None:
            raise KeyError(name)

        glob = ir.GlobalVariable(self, llvm_type, name)
        glob.linkage = linkage
        glob.global_constant = constant

        if initializer is not None:
            glob.initializer = initializer

        variable = RIALVariable(name, rial_type, llvm_type, glob, access_modifier)
        self.global_variables[name] = variable

        return variable

    def declare_function(self, name: str, canonical_name: str, func_type: ir.FunctionType, linkage: str,
                         calling_convention: str, definition: FunctionDefinition):
        func = RIALFunction(self, func_type, name, canonical_name)
        func.linkage = linkage
        func.calling_convention = calling_convention
        func.definition = definition

        return func

    @contextmanager
    def _create_function_body(self, func: RIALFunction):
        with self._enter_function_body(func):
            # Allocate new variables for passed arguments unless they're already pointers
            for i, arg in enumerate(func.args):
                if func.definition.rial_args[i].is_variable:
                    variable = func.definition.rial_args[i]
                else:
                    variable = self.builder.alloca(func.definition.rial_args[i].llvm_type)
                    self.builder.store(arg, variable)
                    variable = RIALVariable(arg.name, func.definition.rial_args[i].rial_type, arg.type, variable)

                self.current_block.add_named_value(arg.name, variable)

            yield

    @contextmanager
    def _enter_function_body(self, func: RIALFunction, block: Optional[LLVMBlock] = None):
        old_func = self.current_func
        old_conditional_block = self.conditional_block
        old_end_block = self.end_block
        old_block = self.current_block
        old_pos = self.builder is not None and self.builder._anchor or 0
        old_unsafe = self.currently_unsafe

        self.current_func = func
        self.currently_unsafe = func.definition.unsafe
        self.conditional_block = None
        self.end_block = None

        if len(func.basic_blocks) == 0:
            # Entry block
            bb = func.append_basic_block("entry")
            self.current_block = bb
        elif block is not None:
            bb = next(([blc for blc in func.basic_blocks if blc.name == block.name]), None)

            if bb is None:
                raise KeyError(bb)
            self.current_block = bb
        else:
            bb = func.basic_blocks[-1]
            self.current_block = bb

        if self.builder is None:
            self.builder = IRBuilder(bb)

        if bb.is_terminated:
            self.builder.position_before(bb.terminator)
        else:
            self.builder.position_at_end(bb)

        yield

        if not self.current_block.is_terminated:
            self.builder.ret_void()

        self.finish_current_func()
        self.current_func = old_func
        self.conditional_block = old_conditional_block
        self.end_block = old_end_block
        self.current_block = old_block
        self.builder._block = self.current_block
        self.builder._anchor = old_pos
        self.currently_unsafe = old_unsafe

    @contextmanager
    def create_or_enter_function_body(self, func: RIALFunction, block: Optional[LLVMBlock] = None):
        if len(func.basic_blocks) == 0:
            with self._create_function_body(func):
                yield
        else:
            with self._enter_function_body(func, block):
                yield

    @contextmanager
    def create_in_global_ctor(self):
        func = self.get_global_safe('global_ctor')

        if func is None:
            func_type = ir.FunctionType(ir.VoidType(), [], False)
            func = self.declare_function('global_ctor', 'global_ctor', func_type, "internal", "ccc",
                                         FunctionDefinition("Void"))
            struct_type = ir.LiteralStructType([Int32, func_type.as_pointer(), ir.IntType(8).as_pointer()])
            glob_value = ir.Constant(ir.ArrayType(struct_type, 1),
                                     [ir.Constant.literal_struct([Int32(65535), func, NULL])])
            glob_type = ir.ArrayType(struct_type, 1)

            self.declare_global("llvm.global_ctors", map_llvm_to_type(glob_type), glob_type, "appending", glob_value)

        with self.create_or_enter_function_body(func):
            yield

    def finish_current_func(self):
        # If we're in release mode
        # Reorder all possible allocas to the start of the function
        from rial.compilation_manager import CompilationManager
        if CompilationManager.config.raw_opts.release:
            entry: Block = self.current_func.entry_basic_block
            pos = entry.instructions.index(
                next((instr for instr in reversed(entry.instructions) if isinstance(instr, AllocaInstr)),
                     entry.terminator))
            allocas: List[Tuple[AllocaInstr, Block]] = list()

            for block in self.current_func.blocks:
                block: Block
                # Skip first block
                if block == entry:
                    continue
                for instr in block.instructions:
                    if isinstance(instr, AllocaInstr):
                        allocas.append((instr, block))
            for instr_block in allocas:
                if instr_block is not None:
                    instr_block[1].instructions.remove(instr_block[0])
                    entry.instructions.insert(pos, instr_block[0])
                    pos += 1
                    # Insert nop if block is empty
                    if len(instr_block[1].instructions) == 0:
                        self.builder.position_before(instr_block[1].terminator)
                        self.builder.gen_no_op()
