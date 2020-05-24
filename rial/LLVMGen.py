from contextlib import contextmanager
from typing import Optional, Union, Tuple, List, Any

from llvmlite import ir
from llvmlite.ir import IRBuilder, AllocaInstr, Branch, FunctionType, Type, PointerType, \
    Argument, CallInstr, Block, Constant, FormattedConstant, GlobalVariable, ConditionalBranch, CastInstr, GEPInstr, \
    Value

from rial.LLVMBlock import LLVMBlock, create_llvm_block
from rial.LLVMUIntType import LLVMUIntType
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import map_llvm_to_type, null, NULL
from rial.compilation_manager import CompilationManager
from rial.concept.name_mangler import mangle_function_name
from rial.metadata.FunctionDefinition import FunctionDefinition
from rial.metadata.RIALFunction import RIALFunction
from rial.metadata.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.metadata.StructDefinition import StructDefinition
from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class LLVMGen:
    builder: Optional[IRBuilder]
    current_func: Optional[RIALFunction]
    conditional_block: Optional[LLVMBlock]
    end_block: Optional[LLVMBlock]
    current_block: Optional[LLVMBlock]
    current_struct: Optional[RIALIdentifiedStructType]
    currently_unsafe: bool

    def __init__(self):
        self.current_block = None
        self.conditional_block = None
        self.end_block = None
        self.current_func = None
        self.builder = None
        self.current_struct = None
        self.currently_unsafe = False

    def _get_by_identifier(self, identifier: str, variable: Optional = None) -> Optional:
        if isinstance(variable, RIALVariable):
            variable = variable.backing_value

        if not variable is None and hasattr(variable, 'type') and isinstance(variable.type, PointerType):
            if isinstance(variable.type.pointee, RIALIdentifiedStructType):
                struct = ParserState.find_struct(variable.type.pointee.name)

                if struct is None:
                    return None

                if not self.check_struct_access_allowed(struct):
                    raise PermissionError(f"Tried accesssing struct {struct.name}")

                prop = struct.definition.properties[identifier]

                if prop is None:
                    return None

                # Check property access
                if not self.check_property_access_allowed(struct, prop[1]):
                    raise PermissionError(f"Tried to access property {prop[1].name} but it was not allowed!")

                variable = self.builder.gep(variable, [ir.Constant(ir.IntType(32), 0),
                                                       ir.Constant(ir.IntType(32), prop[0])])
        else:
            # Search local variables
            variable = self.current_block.get_named_value(identifier)

            # Search for a global variable
            if variable is None:
                glob = ParserState.find_global(identifier)

                # Check if in same module
                if glob is not None:
                    if glob.backing_value.parent.name != ParserState.module().name:
                        glob_current_module = ParserState.module().get_global_safe(glob.name)

                        if glob_current_module is not None:
                            variable = glob_current_module
                        else:
                            # TODO: Check if global access is allowed
                            variable = self.gen_global_new(glob.name, glob, null(glob.llvm_type), glob.access_modifier,
                                                           "external",
                                                           glob.backing_value.global_constant)
                    else:
                        variable = glob.backing_value

        # If variable is none, just do a full function search
        if variable is None:
            variable = ParserState.find_function(identifier)

            if variable is None:
                variable = ParserState.find_function(mangle_function_name(identifier, []))

            # Check if in same module
            if variable is not None:
                if variable.module.name != ParserState.module().name:
                    variable_current_module = ParserState.module().get_global_safe(variable.name)

                    if variable_current_module is not None:
                        variable = variable_current_module
                    else:
                        variable = self.create_function_with_type(variable.name, variable.name, variable.function_type,
                                                                  variable.linkage,
                                                                  variable.calling_convention,
                                                                  variable.definition)

        return variable

    def get_exact_definition(self, identifier: str) -> Optional[Union[RIALFunction, GEPInstr, Value, GlobalVariable]]:
        identifiers = identifier.split('.')
        variable = None

        for ident in identifiers:
            variable = self._get_by_identifier(ident, variable)

        # Search for the full name
        if variable is None:
            variable = self._get_by_identifier(identifier, variable)

        return variable

    def get_definition(self, identifier: str) -> Optional[Union[RIALFunction, GEPInstr, Value, GlobalVariable]]:
        variable = self.get_exact_definition(identifier)

        # Search with module specifier
        if variable is None:
            if ':' in identifier:
                parts = identifier.split(':')
                module_name = ':'.join(parts[0:-1])

                if CompilationManager.check_module_already_compiled(module_name):
                    return None

                if ParserState.add_dependency_and_wait(module_name):
                    return self.get_definition(identifier)

                return None

        return variable

    def gen_integer(self, number: int, length: int, unsigned: bool = False):
        return ir.Constant((unsigned and LLVMUIntType(length) or ir.IntType(length)), number)

    def gen_half(self, number: float):
        return ir.Constant(ir.HalfType(), number)

    def gen_float(self, number: float):
        return ir.Constant(ir.FloatType(), number)

    def gen_double(self, number: float):
        return ir.Constant(ir.DoubleType(), number)

    def gen_global(self, name: str, value: Optional[ir.Constant], ty: Type, access_modifier: RIALAccessModifier,
                   linkage: str,
                   constant: bool):
        rial_variable = ParserState.module().get_rial_variable(name)

        if rial_variable is not None:
            return rial_variable.backing_value

        glob = ir.GlobalVariable(ParserState.module(), ty, name=name)
        glob.linkage = linkage
        glob.global_constant = constant

        if value is not None:
            glob.initializer = value

        rial_variable = RIALVariable(name, map_llvm_to_type(ty), glob, access_modifier)
        ParserState.module().global_variables.append(rial_variable)

        return glob

    def gen_global_new(self, name: str, value: RIALVariable, initializer: Optional[ir.Value],
                       access_modifier: RIALAccessModifier,
                       linkage: str,
                       constant: bool):
        rial_variable = ParserState.module().get_rial_variable(name)

        if rial_variable is not None:
            return rial_variable.backing_value

        glob = ir.GlobalVariable(ParserState.module(), value.llvm_type, name=name)
        glob.linkage = linkage
        glob.global_constant = constant

        if initializer is not None:
            glob.initializer = initializer

        rial_variable = RIALVariable(name, value.rial_type, glob, access_modifier)
        ParserState.module().global_variables.append(rial_variable)

        return rial_variable

    def gen_string_lit(self, name: str, value: str):
        value = eval("'{}'".format(value))

        # TODO: Remove the always-added \0 once we don't need that anymore
        arr = bytearray(value.encode("utf-8") + b"\x00")
        const_char_arr = ir.Constant(ir.ArrayType(ir.IntType(8), len(arr)), arr)
        glob = self.gen_global(name, const_char_arr, const_char_arr.type, RIALAccessModifier.PRIVATE, "private", True)

        return glob

    def gen_load_if_necessary(self, value):
        if isinstance(value, AllocaInstr) or isinstance(value, Argument) or isinstance(value, FormattedConstant) or (
                hasattr(value, 'type') and isinstance(value.type, PointerType)):
            return self.builder.load(value)
        return value

    def gen_var_if_necessary(self, value):
        # Check if variable is not:
        #   - Pointer
        #   - Alloca (Variable), inherently pointer
        #   - Argument (always pointer)
        #   - Type is pointer (e.g. getelementptr instruction)
        if not (isinstance(value, PointerType) or isinstance(value, AllocaInstr) or isinstance(value, Argument)
                or isinstance(value.type, PointerType)):
            allocad = self.builder.alloca(value.type)
            self.builder.store(value, allocad)
            return allocad
        return value

    def gen_addition(self, left, right):
        left = self.gen_load_if_necessary(left)
        right = self.gen_load_if_necessary(right)

        if isinstance(left.type, ir.IntType):
            return self.builder.add(left, right)

        if isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType):
            return self.builder.fadd(left, right)

        return None

    def gen_subtraction(self, left, right):
        left = self.gen_load_if_necessary(left)
        right = self.gen_load_if_necessary(right)

        if isinstance(left.type, ir.IntType):
            return self.builder.sub(left, right)

        if isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType):
            return self.builder.fsub(left, right)

        return None

    def gen_multiplication(self, left, right):
        left = self.gen_load_if_necessary(left)
        right = self.gen_load_if_necessary(right)

        if isinstance(left.type, ir.IntType):
            return self.builder.mul(left, right)

        if isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType):
            return self.builder.fmul(left, right)

        return None

    def gen_division(self, left, right):
        left = self.gen_load_if_necessary(left)
        right = self.gen_load_if_necessary(right)

        if isinstance(left.type, LLVMUIntType):
            return self.builder.udiv(left, right)

        if isinstance(left.type, ir.IntType):
            return self.builder.sdiv(left, right)

        if isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType):
            return self.builder.fdiv(left, right)

        return None

    def gen_comparison(self, comparison: str, left, right):
        left = self.gen_load_if_necessary(left)
        right = self.gen_load_if_necessary(right)

        if isinstance(left.type, LLVMUIntType) or isinstance(left.type, ir.PointerType):
            return self.builder.icmp_unsigned(comparison, left, right)

        if isinstance(left.type, ir.IntType):
            return self.builder.icmp_signed(comparison, left, right)

        if isinstance(left.type, ir.FloatType) or isinstance(left.type, ir.DoubleType):
            return self.builder.fcmp_ordered(comparison, left, right)

        return None

    def gen_shorthand(self, variable, value, operation):
        loaded = self.builder.load(variable)
        value = self.gen_load_if_necessary(value)
        mathed = None

        if operation == "+":
            mathed = self.gen_addition(loaded, value)
        elif operation == "-":
            mathed = self.gen_subtraction(loaded, value)
        elif operation == "*":
            mathed = self.gen_multiplication(loaded, value)
        elif operation == "/":
            mathed = self.gen_division(loaded, value)

        self.builder.store(mathed, variable)

        return mathed

    def gen_function_call(self, possible_function_names: List[str], args: List[RIALVariable]) -> Optional[CallInstr]:
        func = None
        # Check if it's actually a local variable
        for function_name in possible_function_names:
            var = self.get_definition(function_name)

            if var is not None:
                func = var

        # Try to find by function name
        if func is None:
            for function_name in possible_function_names:
                func = ParserState.find_function(function_name)

                if func is not None:
                    break

        # Try to find by function name but enable canonical name
        if func is None:
            rial_arg_types = [arg.rial_type for arg in args]

            for function_name in possible_function_names:
                func = ParserState.find_function(function_name, rial_arg_types)

                if func is not None:
                    break

        if func is None:
            return None

        if isinstance(func, ir.PointerType) and isinstance(func.pointee, RIALFunction):
            func = func.pointee
        elif isinstance(func, RIALVariable):
            if isinstance(func.backing_value, RIALFunction):
                func = func.backing_value
            else:
                loaded_func = self.builder.load(func.backing_value)
                call = self.builder.call(loaded_func, [arg.backing_value for arg in args])
                return call
        elif isinstance(func, ir.GlobalVariable):
            loaded_func = self.builder.load(func)
            call = self.builder.call(loaded_func, [arg.backing_value for arg in args])
            return call

        # Check if call is allowed
        if not self.check_function_call_allowed(func):
            raise PermissionError(f"Tried calling function {func.name} from {self.current_func.name}")

        # Check if function is declared in current module
        if ParserState.module().get_global_safe(func.name) is None:
            func = self.create_function_with_type(func.name, func.canonical_name, func.function_type, func.linkage,
                                                  func.calling_convention, func.definition)

        # Get the LLVM args and match them to the function arguments
        llvm_args = list()

        for i, arg in enumerate(func.definition.rial_args):
            try:
                llvm_args.append(args[i].value_for_rial_type(arg.rial_type))
            except IndexError:
                # Variable args also accept zero args
                if arg.name.endswith("..."):
                    pass
                else:
                    raise

        # Check type matching
        # for i, arg in enumerate(args):
        #     if len(func.args) > i and arg.type != func.args[i].type:
        #         # Check for base types
        #         ty = isinstance(arg.type, PointerType) and arg.type.pointee or arg.type
        #         func_arg_type = isinstance(func.args[i].type, PointerType) and func.args[i].type.pointee or func.args[
        #             i].type
        #
        #         if isinstance(ty, RIALIdentifiedStructType):
        #             struct = ParserState.find_struct(ty.name)
        #
        #             if struct is not None:
        #                 found = False
        #
        #                 # Check if a base struct matches the type expected
        #                 # TODO: Recursive check
        #                 for base_struct in struct.definition.base_structs:
        #                     if base_struct == func_arg_type.name:
        #                         args.remove(arg)
        #                         args.insert(i, self.builder.bitcast(arg, ir.PointerType(base_struct)))
        #                         found = True
        #                         break
        #                 if found:
        #                     continue
        #
        #             # TODO: SLOC information
        #         raise TypeError(
        #             f"Function {func.name} expects a {func.args[i].type} but got a {arg.type}")

        # Gen call
        return self.builder.call(func, llvm_args)

    def gen_no_op(self):
        self.gen_function_call(["rial:builtin:settings:nop_function"], [])

    def check_function_call_allowed(self, func: RIALFunction):
        # Unsafe in safe context is big no-no
        if func.definition.unsafe and not self.currently_unsafe:
            return False
        # Public is always okay
        if func.definition.access_modifier == RIALAccessModifier.PUBLIC:
            return True
        # Internal only when it's the same TLM
        if func.definition.access_modifier == RIALAccessModifier.INTERNAL:
            return func.module.name.split(':')[0] == ParserState.module().name.split(':')[0]
        # Private is harder
        if func.definition.access_modifier == RIALAccessModifier.PRIVATE:
            # Allowed if not in struct and in current module
            if func.definition.struct == "" and func.module.name == ParserState.module().name:
                return True
            # Allowed if in same struct irregardless of module
            if self.current_struct is not None and self.current_struct.name == func.definition.struct:
                return True
        return False

    def check_property_access_allowed(self, struct: RIALIdentifiedStructType, prop: RIALVariable):
        # Same struct, anything goes
        if self.current_struct is not None and self.current_struct.name == struct.name:
            return True

        # Unless it's private it's okay
        if prop.access_modifier == RIALAccessModifier.PRIVATE:
            return False

        return True

    def check_struct_access_allowed(self, struct: RIALIdentifiedStructType):
        # Public is always okay
        if struct.definition.access_modifier == RIALAccessModifier.PUBLIC:
            return True

        # Private and same module
        if struct.definition.access_modifier == RIALAccessModifier.PRIVATE:
            return struct.module_name == ParserState.module().name

        # Internal and same TLM
        if struct.definition.access_modifier == RIALAccessModifier.INTERNAL:
            return struct.module_name.split(':')[0] == ParserState.module().name.split(':')[0]

        return False

    def declare_nameless_variable_from_rial_type(self, rial_type: str, value):
        returned_type = ParserState.map_type_to_llvm_no_pointer(rial_type)

        if isinstance(returned_type, ir.VoidType):
            return value
        returned_value = self.builder.alloca(returned_type)

        if isinstance(ParserState.map_type_to_llvm(rial_type), PointerType):
            self.builder.store(self.builder.load(value), returned_value)
        else:
            self.builder.store(value, returned_value)

        return returned_value

    def assign_non_constant_global_variable(self, glob: GlobalVariable, value):
        if self.current_func.name != "global_ctor":
            raise PermissionError()

        if isinstance(value, AllocaInstr):
            value = self.builder.load(value)
        elif isinstance(value, PointerType):
            value = self.builder.load(value.pointee)
        elif isinstance(value, FormattedConstant):
            value = self.builder.load(value)

        self.builder.store(value, glob)

    def declare_non_constant_global_variable(self, identifier: str, value, access_modifier: RIALAccessModifier,
                                             linkage: str):
        """
        Needs to be called with create_in_global_ctor or otherwise the store/load operations are going to fail.
        :param identifier:
        :param value:
        :param access_modifier:
        :param linkage:
        :return:
        """
        if ParserState.module().get_global_safe(identifier) is not None:
            return None

        if self.current_func.name != "global_ctor":
            return None

        if isinstance(value, AllocaInstr):
            variable = self.gen_global(identifier, null(value.type.pointee), value.type.pointee, access_modifier,
                                       linkage, False)
        elif isinstance(value, PointerType):
            variable = self.gen_global(identifier, null(value.pointee.type), value.pointee.type, access_modifier,
                                       linkage, False)
        elif isinstance(value, FormattedConstant) or isinstance(value, AllocaInstr):
            variable = self.gen_global(identifier, null(value.type.pointee), value.type.pointee, access_modifier,
                                       linkage, False)
        elif isinstance(value, Constant):
            variable = self.gen_global(identifier, null(value.type), value.type, access_modifier, linkage, False)
        else:
            variable = self.gen_global(identifier, null(value.type), value.type, access_modifier, linkage, False)

        self.assign_non_constant_global_variable(variable, value)

        return variable

    def declare_variable(self, identifier: str, value) -> Optional[AllocaInstr]:
        variable = self.current_block.get_named_value(identifier)
        if variable is not None:
            return None

        if isinstance(value, AllocaInstr) or isinstance(value, PointerType):
            variable = value
            variable.name = identifier
        elif isinstance(value, CastInstr) and value.opname == "inttoptr":
            variable = self.builder.alloca(value.type.pointee)
            variable.name = identifier
            rial_type = f"{map_llvm_to_type(value.type)}"
            variable.set_metadata('type',
                                  ParserState.module().add_metadata((rial_type,)))
            self.builder.store(self.builder.load(value), variable)
        elif isinstance(value, FormattedConstant):
            variable = self.builder.alloca(value.type.pointee)
            variable.name = identifier
            rial_type = f"{map_llvm_to_type(value.type)}"
            variable.set_metadata('type',
                                  ParserState.module().add_metadata((rial_type,)))
            self.builder.store(self.builder.load(value), variable)
        elif isinstance(value, Constant):
            variable = self.builder.alloca(value.type)
            variable.name = identifier
            rial_type = f"{map_llvm_to_type(value.type)}"
            variable.set_metadata('type',
                                  ParserState.module().add_metadata((rial_type,)))
            self.builder.store(value, variable)
        else:
            variable = self.builder.alloca(value.type)
            variable.name = identifier
            rial_type = f"{map_llvm_to_type(value.type)}"
            variable.set_metadata('type', ParserState.module().add_metadata((rial_type,)))
            self.builder.store(value, variable)

        self.current_block.add_named_value(identifier, variable)

        return variable

    def assign_to_variable(self, identifier: Union[str, Any], value):
        if isinstance(identifier, str):
            variable = self.get_definition(identifier)
        else:
            variable = identifier

        if variable is None:
            return None

        if isinstance(value, AllocaInstr):
            value = self.builder.load(value)
        elif isinstance(value, PointerType) and not isinstance(variable, PointerType):
            value = self.builder.load(value.pointee)

        self.builder.store(value, variable)

        return variable

    def create_block(self, block_name: str, parent: Optional[LLVMBlock] = None,
                     sibling: Optional[LLVMBlock] = None) -> \
            Optional[LLVMBlock]:
        if parent is None and sibling is None and block_name != "entry" and len(self.current_func.basic_blocks) > 0:
            return None

        block = self.builder.append_basic_block(block_name)
        llvmblock = create_llvm_block(block, parent, sibling)

        return llvmblock

    def create_loop(self, base_block_name: str, parent: LLVMBlock):
        (conditional_llvm_block, body_llvm_block, end_llvm_block) = self.create_conditional_block(base_block_name,
                                                                                                  parent)

        self.conditional_block = conditional_llvm_block
        self.end_block = end_llvm_block

        return conditional_llvm_block, body_llvm_block, end_llvm_block,

    def create_switch_blocks(self, base_block_name: str, parent: LLVMBlock, count_of_cases: int,
                             default_case: bool) -> \
            List[LLVMBlock]:
        blocks = list()

        for i in range(0, count_of_cases):
            blocks.append(self.create_block(f"{base_block_name}.case.{i}", parent, None))

        if default_case:
            blocks.append(self.create_block(f"{base_block_name}.default", parent))

        return blocks

    def create_conditional_block(self, base_block_name: str, parent: LLVMBlock) -> Tuple[
        LLVMBlock, LLVMBlock, LLVMBlock]:
        # Create three blocks, one condition, one body, and one after the loop
        conditional_llvm_block = self.create_block(f"{base_block_name}.condition", parent, None)
        body_llvm_block = self.create_block(f"{base_block_name}.body", conditional_llvm_block, None)
        end_llvm_block = self.create_block(f"{base_block_name}.end", None, parent)

        return conditional_llvm_block, body_llvm_block, end_llvm_block,

    def create_conditional_block_with_else(self, base_block_name: str, parent: LLVMBlock):
        (conditional_block, body_block, else_block) = self.create_conditional_block(base_block_name, parent)

        # Transform end block into else block
        else_block.block.name = f"{base_block_name}.else"
        else_block.sibling = None
        else_block.parent = conditional_block

        # Create new end block
        end_block = self.create_block(f"{base_block_name}.if_else.end", None, conditional_block.parent)

        return conditional_block, body_block, else_block, end_block

    def create_jump_if_not_exists(self, target_block: LLVMBlock) -> Optional[Branch]:
        if self.current_block.block.terminator is None:
            return self.builder.branch(target_block.block)

        return None

    def create_conditional_jump(self, condition, true_block: LLVMBlock, false_block: LLVMBlock,
                                true_branch_weight: int = 50, false_branch_weight: int = 50) -> ConditionalBranch:
        cbranch = self.builder.cbranch(condition, true_block.block, false_block.block)

        cbranch.set_weights([true_branch_weight, false_branch_weight])

        return cbranch

    def create_jump(self, target_block: LLVMBlock):
        return self.builder.branch(target_block.block)

    def enter_block(self, llvmblock: LLVMBlock):
        self.current_block = llvmblock
        self.builder.position_at_start(self.current_block.block)

    def enter_block_end(self, llvmblock: LLVMBlock):
        self.current_block = llvmblock
        self.builder.position_at_end(self.current_block.block)

    def create_identified_struct(self, name: str, linkage: str,
                                 rial_access_modifier: RIALAccessModifier,
                                 base_llvm_structs: List[RIALIdentifiedStructType],
                                 body: List[RIALVariable]) -> RIALIdentifiedStructType:
        # Build normal struct and switch out with RIALStruct
        struct = ParserState.module().context.get_identified_type(name)
        rial_struct = RIALIdentifiedStructType(struct.context, struct.name, struct.packed)
        ParserState.module().context.identified_types[struct.name] = rial_struct
        struct = rial_struct
        ParserState.module().structs.append(struct)

        # Create metadata definition
        struct_def = StructDefinition(rial_access_modifier)

        # Build body and body definition
        props_def = dict()
        props = list()
        prop_offset = 0
        for deriv in base_llvm_structs:
            for prop in deriv.definition.properties.values():
                props.append(ParserState.map_type_to_llvm(prop[1].rial_type))
                props_def[prop[1].name] = (prop_offset, prop[1])
                prop_offset += 1

            struct_def.base_structs.append(deriv.name)
        for bod in body:
            props.append(ParserState.map_type_to_llvm(bod.rial_type))
            props_def[bod.name] = (prop_offset, bod)
            prop_offset += 1

        struct.set_body(*tuple(props))
        struct.module_name = ParserState.module().name
        self.current_struct = struct

        struct_def.properties = props_def

        # Store def in metadata
        struct.definition = struct_def

        return struct

    def finish_struct(self):
        self.current_struct = None
        self.current_func = None
        self.current_block = None

    def create_function_with_type(self, name: str, canonical_name: str, ty: FunctionType,
                                  linkage: str,
                                  calling_convention: str,
                                  function_def: FunctionDefinition) -> RIALFunction:
        """
        Creates an IR Function with the specified arguments. NOTHING MORE.
        :param canonical_name:
        :param function_def:
        :param name:
        :param ty:
        :param linkage:
        :param calling_convention:
        :param arg_names:
        :return:
        """

        # Create function with specified linkage (internal -> module only)
        func = RIALFunction(ParserState.module(), ty, name=name, canonical_name=canonical_name)
        func.linkage = linkage
        func.calling_convention = calling_convention
        func.definition = function_def

        # Set argument names
        for i, arg in enumerate(func.args):
            arg.name = function_def.rial_args[i].name

        return func

    def create_function_body(self, func: RIALFunction, rial_arg_types: List[str]):
        self.current_func = func

        # Create entry block
        bb = func.append_basic_block("entry")
        llvm_bb = create_llvm_block(bb)
        self.current_block = llvm_bb

        if self.builder is None:
            self.builder = IRBuilder(bb)

        self.builder.position_at_start(bb)

        # Allocate new variables for the passed arguments
        for i, arg in enumerate(func.args):
            # Don't copy variables that are a pointer
            if isinstance(arg.type, PointerType):
                self.current_block.named_values[arg.name] = arg
                continue
            allocated_arg = self.builder.alloca(arg.type)
            self.builder.store(arg, allocated_arg)
            self.current_block.named_values[arg.name] = allocated_arg
            allocated_arg.set_metadata('type',
                                       ParserState.module().add_metadata((rial_arg_types[i],)))

    def finish_current_block(self):
        if self.current_block.block.terminator is None:
            self.builder.position_at_end(self.current_block.block)
            self.builder.ret_void()
        self.current_block = self.current_block.parent

    def finish_current_func(self):
        # If we're in release mode
        # Reorder all possible allocas to the start of the function
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
                        self.gen_no_op()
        self.current_func = None

    def create_return_statement(self, statement: RIALVariable):
        if statement.is_void:
            return self.builder.ret_void()

        # Return the actual value if the return type is not a pointer
        if not isinstance(self.current_func.function_type.return_type, ir.PointerType):
            return self.builder.ret(statement.value_for_calculations)
        return self.builder.ret(statement.backing_value)

    def finish_loop(self):
        self.conditional_block = None
        self.end_block = None

    def create_function_type(self, llvm_return_type: Type, llvm_arg_types: List[Type], var_args: bool):
        return ir.FunctionType(llvm_return_type, tuple(llvm_arg_types), var_arg=var_args)

    @contextmanager
    def create_in_global_ctor(self):
        current_block = self.current_block
        current_func = self.current_func
        current_struct = self.current_struct
        conditional_block = self.conditional_block
        end_block = self.end_block
        pos = self.builder is not None and self.builder._anchor or 0

        func = ParserState.module().get_global_safe('global_ctor')

        if func is None:
            func_type = self.create_function_type(ir.VoidType(), [], False)
            func = self.create_function_with_type('global_ctor', 'global_ctor', func_type, "internal", "ccc",
                                                  FunctionDefinition('void'))
            self.create_function_body(func, [])
            struct_type = ir.LiteralStructType([ir.IntType(32), func_type.as_pointer(), ir.IntType(8).as_pointer()])
            glob_value = ir.Constant(ir.ArrayType(struct_type, 1), [ir.Constant.literal_struct(
                [ir.Constant(ir.IntType(32), 65535), func, NULL])])
            glob_type = ir.ArrayType(struct_type, 1)

            self.gen_global("llvm.global_ctors", glob_value, glob_type, RIALAccessModifier.PRIVATE, "appending", False)
        else:
            self.builder.position_before(func.entry_basic_block.terminator)
            self.current_func = func
            self.current_block = create_llvm_block(func.entry_basic_block)

        self.current_struct = None
        self.conditional_block = None
        self.end_block = None

        yield

        self.finish_current_block()
        self.finish_current_func()

        self.current_block = current_block
        self.current_func = current_func
        self.current_struct = current_struct
        self.conditional_block = conditional_block
        self.end_block = end_block
        self.builder._anchor = pos
        self.builder._block = self.current_block is not None and self.current_block.block or None

        return
