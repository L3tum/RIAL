from typing import Optional, Union, Tuple, List, Literal, Dict, Any

from llvmlite import ir
from llvmlite.ir import IRBuilder, Function, AllocaInstr, Branch, FunctionType, Type, VoidType, PointerType, \
    Argument, CallInstr, Block, IdentifiedStructType

from rial.LLVMBlock import LLVMBlock, create_llvm_block
from rial.LLVMUIntType import LLVMUIntType
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import map_llvm_to_type
from rial.compilation_manager import CompilationManager
from rial.metadata.FunctionDefinition import FunctionDefinition
from rial.metadata.StructDefinition import StructDefinition
from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class LLVMGen:
    builder: Optional[IRBuilder]
    current_func: Optional[Function]
    conditional_block: Optional[LLVMBlock]
    end_block: Optional[LLVMBlock]
    current_block: Optional[LLVMBlock]
    current_struct: Optional[IdentifiedStructType]
    global_variables: Dict

    def __init__(self):
        self.current_block = None
        self.conditional_block = None
        self.end_block = None
        self.current_func = None
        self.builder = None
        self.current_struct = None
        self.global_variables = dict()

    def get_var(self, identifier: str):
        identifiers = identifier.split('.')
        variable = None

        for ident in identifiers:
            if not variable is None and isinstance(variable.type, PointerType):
                if isinstance(variable.type.pointee, IdentifiedStructType):
                    struct = ParserState.find_struct(variable.type.pointee.name)

                    if struct is None:
                        return None

                    struct_def = StructDefinition.from_mdvalue(
                        struct.module.get_named_metadata(f"{struct.name.replace(':', '_')}.definition"))

                    if not self.check_struct_access_allowed(struct, struct_def):
                        raise PermissionError(f"Tried accesssing struct {struct.name}")

                    prop = struct_def.properties[ident]

                    if prop is None:
                        return None

                    # Check property access
                    if not self.check_property_access_allowed(struct, prop[1]):
                        raise PermissionError(f"Tried to access property {prop[1].name} but it was not allowed!")

                    variable = self.builder.gep(variable, [ir.Constant(ir.IntType(32), 0),
                                                           ir.Constant(ir.IntType(32), prop[0])])
            else:
                variable = self.current_block.get_named_value(ident)

        return variable

    def gen_integer(self, number: int, length: int, unsigned: bool = False):
        return ir.Constant((unsigned and LLVMUIntType(length) or ir.IntType(length)), number)

    def gen_half(self, number: float):
        return ir.Constant(ir.HalfType(), number)

    def gen_float(self, number: float):
        return ir.Constant(ir.FloatType(), number)

    def gen_double(self, number: float):
        return ir.Constant(ir.DoubleType(), number)

    def gen_string_lit(self, name: str, value: str):
        value = eval("'{}'".format(value))

        # TODO: Remove the always-added \0 once we don't need that anymore
        arr = bytearray(value.encode("utf-8") + b"\x00")
        const_char_arr = ir.Constant(ir.ArrayType(ir.IntType(8), len(arr)), arr)
        glob = ir.GlobalVariable(ParserState.module(), const_char_arr.type, name=name)
        glob.linkage = 'private'
        glob.global_constant = True
        glob.initializer = const_char_arr
        glob.unnamed_addr = True

        return glob

    def gen_load_if_necessary(self, value):
        if isinstance(value, AllocaInstr) or isinstance(value, Argument) or (
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

        if isinstance(left.type, LLVMUIntType):
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

    def gen_function_call(self, possible_function_names: List[str],
                          llvm_args: List) -> Optional[CallInstr]:
        func = None

        # Try to find by function name
        for function_name in possible_function_names:
            func = ParserState.find_function(function_name)

            if func is not None:
                break

        if func is None:
            return None

        func_def: FunctionDefinition = func.get_function_definition()

        # Check if call is allowed
        if not self.check_function_call_allowed(func, func_def):
            raise PermissionError(f"Tried calling function {func.name} from {self.current_func.name}")

        # Check if function is declared in current module
        if ParserState.module().get_global_safe(func.name) is None:
            func = self.create_function_with_type(func.name, func.function_type, func.linkage, func.calling_convention,
                                                  [arg.name for arg in func.args], func_def)

        args = list()

        # Gen a load if it doesn't expect a pointer
        for i, arg in enumerate(llvm_args):
            # If it's a variable and the function doesn't expect a pointer we _need_ to load it
            if isinstance(arg, AllocaInstr) and (len(func.args) <= i or not isinstance(func.args[i].type, PointerType)):
                args.append(self.gen_load_if_necessary(arg))
            elif len(func.args) > i and not isinstance(func.args[i].type, PointerType):
                args.append(self.gen_load_if_necessary(arg))
            else:
                args.append(arg)

        # Check type matching
        for i, arg in enumerate(args):
            if len(func.args) > i and arg.type != func.args[i].type:
                # Check for base types
                ty = isinstance(arg.type, PointerType) and arg.type.pointee or arg.type
                func_arg_type = isinstance(func.args[i].type, PointerType) and func.args[i].type.pointee or func.args[
                    i].type
                struct = ParserState.find_struct(ty.name)

                if struct is not None:
                    struct_def: StructDefinition = struct.get_struct_definition()
                    found = False

                    # Check if a base struct matches the type expected
                    # TODO: Recursive check
                    for base_struct in struct_def.base_structs:
                        if base_struct == func_arg_type.name:
                            args.remove(arg)
                            args.insert(i, self.builder.bitcast(arg, ir.PointerType(base_struct)))
                            found = True
                            break
                    if found:
                        continue

                    # TODO: SLOC information
                raise TypeError(
                    f"Function {func.name} expects a {map_llvm_to_type(func.args[i].type)} but got a {map_llvm_to_type(arg.type)}")

        # Gen call
        return self.builder.call(func, args)

    def gen_no_op(self):
        # Redeclare llvm.donothing if it isn't declared in current module
        try:
            ParserState.module().get_global('llvm.donothing')
        except KeyError:
            func_type = self.create_function_type(ir.VoidType(), [], False)
            self.create_function_with_type('llvm.donothing', func_type, "external", "", [],
                                           FunctionDefinition("void", RIALAccessModifier.PUBLIC, []))

        self.gen_function_call(["llvm.donothing"], [])

    def check_function_call_allowed(self, func: Function, func_def: FunctionDefinition):
        # Public is always okay
        if func_def.access_modifier == RIALAccessModifier.PUBLIC:
            return True
        # Internal only when it's the same TLM
        if func_def.access_modifier == RIALAccessModifier.INTERNAL:
            return func.module.name.split(':')[0] == ParserState.module().name.split(':')[0]
        # Private is harder
        if func_def.access_modifier == RIALAccessModifier.PRIVATE:
            # Allowed if not in struct and in current module
            if func_def.struct == "" and func.module.name == ParserState.module().name:
                return True
            # Allowed if in same struct irregardless of module
            if self.current_struct is not None and self.current_struct.name == func_def.struct:
                return True
        return False

    def check_property_access_allowed(self, struct: IdentifiedStructType, prop: RIALVariable):
        # Same struct, anything goes
        if self.current_struct is not None and self.current_struct.name == struct.name:
            return True

        # Unless it's private it's okay
        if prop.access_modifier == RIALAccessModifier.PRIVATE:
            return False

        return True

    def check_struct_access_allowed(self, struct: IdentifiedStructType, struct_def: StructDefinition):
        # Public is always okay
        if struct_def.access_modifier == RIALAccessModifier.PUBLIC:
            return True

        # Private and same module
        if struct_def.access_modifier == RIALAccessModifier.PRIVATE:
            return struct.module.name == ParserState.module().name

        # Internal and same TLM
        if struct_def.access_modifier == RIALAccessModifier.INTERNAL:
            return struct.module.name.split(':')[0] == ParserState.module().name.split(':')[0]

        return False

    def declare_variable(self, identifier: str, variable_type, value, rial_type: str) -> Optional[AllocaInstr]:
        variable = self.current_block.get_named_value(identifier)

        if variable is not None:
            return None

        if isinstance(variable_type, PointerType) and value is not None and isinstance(value.type, PointerType):
            variable = value
            variable.name = identifier
        else:
            variable = self.builder.alloca(variable_type)
            variable.name = identifier
            variable.set_metadata('type',
                                  ParserState.module().add_metadata((rial_type,)))
            if value is not None:
                self.builder.store(value, variable)

        self.current_block.add_named_value(identifier, variable is None and value or variable)

        return variable

    def assign_to_variable(self, identifier: Union[str, Any], value):
        if isinstance(identifier, str):
            variable = self.get_var(identifier)
        else:
            variable = identifier

        if variable is None:
            return None

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

    def create_conditional_jump(self, condition, true_block: LLVMBlock, false_block: LLVMBlock):
        # Check if condition is a variable, we need to load that for LLVM
        condition = self.gen_load_if_necessary(condition)
        return self.builder.cbranch(condition, true_block.block, false_block.block)

    def create_jump(self, target_block: LLVMBlock):
        return self.builder.branch(target_block.block)

    def enter_block(self, llvmblock: LLVMBlock):
        self.current_block = llvmblock
        self.builder.position_at_start(self.current_block.block)

    def enter_block_end(self, llvmblock: LLVMBlock):
        self.current_block = llvmblock
        self.builder.position_at_end(self.current_block.block)

    def create_identified_struct(self, name: str, linkage: Union[Literal["internal"], Literal["external"]],
                                 rial_access_modifier: RIALAccessModifier,
                                 base_llvm_structs: List[IdentifiedStructType],
                                 body: List[RIALVariable]) -> IdentifiedStructType:
        struct = ParserState.module().context.get_identified_type(name)

        # Create metadata definition
        struct_def = StructDefinition(rial_access_modifier)

        # Build body and body definition
        props_def = dict()
        props = list()
        prop_offset = 0
        for deriv in base_llvm_structs:
            stru_def: StructDefinition = deriv.get_struct_definition()

            for prop in stru_def.properties.values():
                props.append(ParserState.map_type_to_llvm(prop[1].rial_type))
                props_def[prop[1].name] = (prop_offset, prop[1])
                prop_offset += 1

            struct_def.base_structs.append(deriv.name)
        for bod in body:
            props.append(ParserState.map_type_to_llvm(bod.rial_type))
            props_def[bod.name] = (prop_offset, bod)
            prop_offset += 1

        struct.set_body(*tuple(props))
        struct.module = ParserState.module()
        self.current_struct = struct

        struct_def.properties = props_def

        # Create base constructor
        function_type = self.create_function_type(ir.VoidType(), [ir.PointerType(struct)], False)
        func = self.create_function_with_type(f"{name}.constructor", function_type, linkage, "", ["this"],
                                              FunctionDefinition(name, rial_access_modifier, [("this", name), ],
                                                                 name))
        struct_def.functions.append(func.name)
        self.create_function_body(func, [name])
        self_value = func.args[0]

        # Call derived constructors
        for deriv in base_llvm_structs:
            constructor_name = f"{deriv.name}.constructor"
            self.gen_function_call([constructor_name], [self.builder.bitcast(self_value, ir.PointerType(deriv)), ])

        # Set initial values
        for bod in body:
            index = props_def[bod.name][0]
            loaded_var = self.builder.gep(self_value,
                                          [ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), index)])
            self.builder.store(bod.initial_value, loaded_var)

        # Store def in metadata
        ParserState.module().update_named_metadata(f"{name.replace(':', '_')}.definition", struct_def.to_list())

        self.builder.ret_void()

        return struct

    def finish_struct(self):
        self.current_struct = None
        self.current_func = None
        self.current_block = None

    def create_function_with_type(self, name: str, ty: FunctionType,
                                  linkage: Union[Literal["internal"], Literal["external"]],
                                  calling_convention: str,
                                  arg_names: List[str],
                                  function_def: FunctionDefinition):
        """
        Creates an IR Function with the specified arguments. NOTHING MORE.
        :param function_def:
        :param name:
        :param ty:
        :param linkage:
        :param calling_convention:
        :param arg_names:
        :return:
        """

        # Create function with specified linkage (internal -> module only)
        func = ir.Function(ParserState.module(), ty, name=name)
        func.linkage = linkage
        func.calling_convention = calling_convention

        if not f"function_definition_{name.replace(':', '_')}" in ParserState.module().namedmetadata:
            ParserState.module().update_named_metadata(f"function_definition_{name.replace(':', '_')}",
                                                       ParserState.module().add_metadata(
                                                           tuple(function_def.to_list())))

        # Set argument names
        for i, arg in enumerate(func.args):
            arg.name = arg_names[i]

        return func

    def create_function_body(self, func: Function, rial_arg_types: List[str]):
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
                        self.builder.position_at_end(instr_block[1])
                        self.gen_no_op()
        self.current_func = None

    def create_return_statement(self, statement):
        if isinstance(statement, VoidType):
            return self.builder.ret_void()

        return self.builder.ret(statement)

    def finish_loop(self):
        self.conditional_block = None
        self.end_block = None

    def create_function_type(self, llvm_return_type: Type, llvm_arg_types: List[Type], var_args: bool):
        return ir.FunctionType(llvm_return_type, tuple(llvm_arg_types), var_arg=var_args)
