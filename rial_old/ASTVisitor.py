from typing import Optional, List

from llvmlite import ir

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import NULL, get_size, Int32, convert_number_to_constant, \
    is_builtin_type
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.concept.only_allowed_in_unsafe import only_allowed_in_unsafe
from rial.concept.parser import Interpreter, Tree, Token
from rial.log import log_fail, log_warn
from rial.metadata.RIALFunction import RIALFunction
from rial.rial_types.RIALVariable import RIALVariable
from rial.type_casting import get_casting_function


class ASTVisitor(Interpreter):
    llvmgen: LLVMGen

    def __init__(self):
        super().__init__()
        self.llvmgen = ParserState.llvmgen()

    def transform_helper(self, node):
        if isinstance(node, Tree):
            node = self.visit(node)

        return node

    def number(self, tree: Tree):
        nodes = tree.children
        value: str = nodes[0].value
        return convert_number_to_constant(value)

    def equal(self, tree: Tree):
        nodes = tree.children
        left: RIALVariable = self.transform_helper(nodes[0])
        comparison = nodes[1].value
        right: RIALVariable = self.transform_helper(nodes[2])

        if left.is_pointer and right.is_pointer and not (left.is_primitive and right.is_primitive):
            result = self.llvmgen.gen_comparison(comparison, left.backing_value, right.backing_value)
        else:
            result = self.llvmgen.gen_comparison(comparison, left.raw_backing_value, right.raw_backing_value)

        if result is None:
            print(comparison)
            print(left.backing_value.type)
            print(right.backing_value.type)

        return RIALVariable(comparison, "Int1", result)

    def sizeof(self, tree: Tree):
        nodes = tree.children
        variable: Optional[RIALVariable] = self.transform_helper(nodes[0])
        name = ""

        # If it's not a variable, extract the name manually since it's the name of a type to get the size of
        if variable is None:
            name = nodes[0].children[0].value
            ty = ParserState.map_type_to_llvm_no_pointer(name)

            size = Int32(get_size(ty))
        elif isinstance(variable.backing_value, ir.GEPInstr) or (
                variable.is_array and isinstance(variable.raw_llvm_type, ir.PointerType)):
            # This is worst case as it cannot be optimized away.
            base = self.llvmgen.builder.ptrtoint(
                self.llvmgen.builder.gep(variable.backing_value, [ir.Constant(ir.IntType(32), 0)]),
                ir.IntType(32))
            val = self.llvmgen.builder.ptrtoint(
                self.llvmgen.builder.gep(variable.backing_value, [ir.Constant(ir.IntType(32), 1)]),
                ir.IntType(32))
            size = self.llvmgen.builder.sub(val, base)
            name = "unknown"
        elif variable.is_array:
            if variable.is_constant_sized_array:
                ty = variable.raw_llvm_type
                size = get_size(ty.element) * ty.count
                size = Int32(size)
                name = f"{ty.element}[{ty.count}]"
            else:
                value = variable.raw_backing_value
                size = get_size(value.type.element)
                size = self.llvmgen.gen_multiplication(Int32(size),
                                                       self.llvmgen.gen_load_if_necessary(value.type.count))
                name = f"{value.type.element}[{value.type.count}]"
        elif variable.raw_llvm_type == variable.raw_backing_value.type:
            size = Int32(get_size(variable.raw_llvm_type))
            name = f"{variable.rial_type}"
        else:
            # This is worst case as it cannot be optimized away.
            base = self.llvmgen.builder.ptrtoint(
                self.llvmgen.builder.gep(variable.backing_value, [ir.Constant(ir.IntType(32), 0)]),
                ir.IntType(32))
            val = self.llvmgen.builder.ptrtoint(
                self.llvmgen.builder.gep(variable.backing_value, [ir.Constant(ir.IntType(32), 1)]),
                ir.IntType(32))
            size = self.llvmgen.builder.sub(val, base)
            name = "unknown"

        return RIALVariable(f"sizeof_{name}", "Int32", size)

    def array_constructor(self, tree: Tree):
        nodes = tree.children
        name = nodes[0].value
        number: RIALVariable = self.transform_helper(nodes[1])

        if isinstance(number.raw_backing_value, ir.Constant):
            number = number.raw_backing_value.constant
        else:
            number = number.raw_backing_value

        ty = ParserState.map_type_to_llvm_no_pointer(name)
        arr_type = ir.ArrayType(ty, number)

        allocated = self.llvmgen.builder.alloca(arr_type)

        return RIALVariable(f"array_{name}[{number}]", f"{name}[{isinstance(number, int) and f'{number}' or ''}]",
                            allocated)

    def array_assignment(self, tree: Tree):
        nodes = tree.children
        entry: RIALVariable = self.transform_helper(nodes[0])
        val: RIALVariable = self.transform_helper(nodes[2])

        if entry.rial_type != val.rial_type:
            raise TypeError(entry, val)

        self.llvmgen.builder.store(val.raw_backing_value, entry.backing_value)

        return val

    def array_access(self, tree: Tree):
        nodes = tree.children
        variable: RIALVariable = self.transform_helper(nodes[0])
        index: RIALVariable = self.transform_helper(nodes[1])

        if not variable.is_array:
            raise TypeError(variable)

        # Check if an array or a pointer to the first element of an array
        if variable.is_pointer and not isinstance(variable.backing_value.type.pointee, ir.ArrayType):
            indices = [index.raw_backing_value]
        else:
            indices = [Int32(0), index.raw_backing_value]

        var = self.llvmgen.builder.gep(variable.backing_value, indices)

        return RIALVariable(f"{variable.name}[{index}]", variable.array_type, var)

    def var(self, tree: Tree):
        if isinstance(tree, Tree):
            nodes = tree.children
        else:
            nodes = [tree]
        token: Token

        if isinstance(nodes[0], Tree):
            identifier = '.'.join([node.value for node in nodes[0].children])
            token = nodes[0].children[0]
        elif isinstance(nodes, list):
            identifier = '.'.join([node.value for node in nodes])
            token = nodes[0]
        else:
            identifier = nodes[0].value
            token = nodes[0]

        return self.llvmgen.get_definition(identifier)

    def math(self, tree: Tree):
        nodes = tree.children

        left: RIALVariable = self.transform_helper(nodes[0])
        op = nodes[1].type
        right: RIALVariable = self.transform_helper(nodes[2])

        if left.rial_type != right.rial_type:
            raise TypeError(str(left), op, str(right))

        left_val = left.raw_backing_value
        right_val = right.raw_backing_value

        result = None

        if op == "PLUS":
            result = self.llvmgen.gen_addition(left_val, right_val)
        elif op == "MINUS":
            result = self.llvmgen.gen_subtraction(left_val, right_val)
        elif op == "MUL":
            result = self.llvmgen.gen_multiplication(left_val, right_val)
        elif op == "DIV":
            result = self.llvmgen.gen_division(left_val, right_val)

        return RIALVariable(f"{left}{op}{right}", left.rial_type, result)

    def variable_assignment(self, tree: Tree):
        nodes = tree.children

        variable: RIALVariable = self.transform_helper(nodes[0])
        value: RIALVariable = self.transform_helper(nodes[2])

        if isinstance(value, RIALFunction):
            value: RIALFunction
            self.llvmgen.builder.store(self.llvmgen.builder.load(value), variable.backing_value)
            return variable

        if variable.rial_type != value.rial_type:
            raise TypeError(str(variable), str(value))

        if value.is_pointer:
            value.name = variable.name
            self.llvmgen.current_block.add_named_value(variable.name, value)
            return value
        else:
            self.llvmgen.builder.store(value.raw_backing_value, variable.backing_value)
            return variable

    def global_variable_assignment(self, tree: Tree):
        nodes = tree.children[0].children

        with self.llvmgen.create_in_global_ctor():
            variable: RIALVariable = self.transform_helper(nodes[0])
            value: RIALVariable = self.transform_helper(nodes[2])

            if variable.rial_type != value.rial_type:
                raise TypeError(variable, value)

            self.llvmgen.builder.store(value.raw_backing_value, variable.backing_value)
            return value

    def variable_decl(self, tree: Tree):
        nodes = tree.children
        identifier = nodes[0].value
        value: RIALVariable = self.transform_helper(nodes[2])

        if isinstance(value, RIALFunction):
            value: RIALFunction
            ty = value.function_type
            raw_value = self.llvmgen.builder.load(value)
            rial_type = str(value.function_type).replace("i8*", "CString")
        else:
            ty: ir.Type = value.raw_llvm_type
            raw_value = value.raw_backing_value
            rial_type = value.rial_type

            if not value.rial_type == "CString" and isinstance(ty, ir.ArrayType):
                ty: ir.ArrayType
                if isinstance(raw_value.type, ir.ArrayType):
                    ty = raw_value.type
                else:
                    ty = ty.element.as_pointer()
                    raw_value = self.llvmgen.builder.gep(value.backing_value, [Int32(0), Int32(0)])

        if isinstance(raw_value.type, ir.IntType) and raw_value.type.width == 8:
            print(raw_value, value)

        variable = self.llvmgen.builder.alloca(ty)
        variable.name = identifier
        self.llvmgen.builder.store(raw_value, variable)
        variable = RIALVariable(identifier, rial_type, variable)
        self.llvmgen.current_block.add_named_value(identifier, variable)

        return variable

    def cast(self, tree: Tree):
        nodes = tree.children
        ty = ParserState.map_type_to_llvm_no_pointer(nodes[0])
        value: RIALVariable = self.transform_helper(nodes[1])

        if is_builtin_type(nodes[0]):
            # Simple cast for primitive to primitive
            if value.is_primitive:
                cast_function = get_casting_function(value.raw_llvm_type, ty)

                if hasattr(self.llvmgen.builder, cast_function):
                    casted = getattr(self.llvmgen.builder, cast_function)(value.raw_backing_value, ty)
                else:
                    raise TypeError(f"No casting function found for casting {value.rial_type} to {nodes[0]}")
            else:
                # Casting type to integer ("pointer") (unsafe!)
                with only_allowed_in_unsafe():
                    casted = self.llvmgen.builder.ptrtoint(value.backing_value, ty)
        else:
            # Casting integer to type (unsafe!)
            if value.is_primitive:
                with only_allowed_in_unsafe():
                    casted = self.llvmgen.builder.inttoptr(value.raw_backing_value, ty.as_pointer())
            else:
                # Simple type cast
                casted = self.llvmgen.builder.bitcast(value.backing_value, ty.as_pointer())

        return RIALVariable(f"cast_{value.rial_type}_to_{nodes[0]}", nodes[0], casted)

    def continue_rule(self, tree: Tree):
        if self.llvmgen.conditional_block is None:
            log_fail(f"'continue' outside of loop")
            return None

        return self.llvmgen.create_jump(self.llvmgen.conditional_block)

    def break_rule(self, tree: Tree):
        if self.llvmgen.end_block is None:
            log_fail(f"'break' outside of loop or conditional block")
            return None

        return self.llvmgen.create_jump(self.llvmgen.end_block)

    def return_rule(self, tree: Tree):
        nodes = tree.children

        if self.llvmgen.current_block.block.terminator is not None:
            log_fail(f"'return' after return found!")
            return None

        variable: RIALVariable = self.transform_helper(nodes[0])

        if variable.rial_type != self.llvmgen.current_func.definition.rial_return_type:
            raise TypeError(variable, self.llvmgen.current_func.definition.rial_return_type)

        if isinstance(variable.raw_llvm_type, ir.VoidType):
            self.llvmgen.builder.ret_void()
        elif variable.is_primitive:
            self.llvmgen.builder.ret(variable.raw_backing_value)
        else:
            self.llvmgen.builder.ret(variable.backing_value)

        return variable

    def loop_loop(self, tree: Tree):
        nodes = tree.children
        name = self.llvmgen.current_block.block.name

        (conditional_block, body_block, end_block) = self.llvmgen.create_loop(name,
                                                                              self.llvmgen.current_block)

        # Remove conditional block again (there's no condition)
        self.llvmgen.current_func.basic_blocks.remove(conditional_block.block)
        self.llvmgen.conditional_block = body_block
        del conditional_block

        # Go into body
        self.llvmgen.create_jump(body_block)
        self.llvmgen.enter_block(body_block)

        # Build body
        for node in nodes:
            self.transform_helper(node)

        # Jump back into body
        self.llvmgen.create_jump_if_not_exists(body_block)

        # Go out of loop
        self.llvmgen.enter_block(end_block)

    def for_loop(self, tree: Tree):
        nodes = tree.children
        name = self.llvmgen.current_block.block.name
        name = f"{name}.wrapper"

        wrapper_block = self.llvmgen.create_block(name, parent=self.llvmgen.current_block)
        (conditional_block, body_block, end_block) = self.llvmgen.create_loop(name, wrapper_block)

        # Move end_block out of wrapper block
        end_block.sibling = self.llvmgen.current_block

        # Create variable in wrapper block
        self.llvmgen.create_jump(wrapper_block)
        self.llvmgen.enter_block(wrapper_block)
        self.transform_helper(nodes[0])

        # Enter conditional block
        self.llvmgen.create_jump(conditional_block)
        self.llvmgen.enter_block(conditional_block)

        # Build condition
        condition: RIALVariable = self.transform_helper(nodes[1])
        self.llvmgen.create_conditional_jump(condition.raw_backing_value, body_block, end_block)

        # Go into body
        self.llvmgen.enter_block(body_block)

        # Build body
        i = 3
        while i < len(nodes):
            self.transform_helper(nodes[i])
            i += 1

        # Build incrementor if no terminator yet
        if self.llvmgen.current_block.block.terminator is None:
            self.transform_helper(nodes[2])

        # Jump back into condition
        self.llvmgen.create_jump_if_not_exists(conditional_block)

        # Go out of loop
        self.llvmgen.enter_block(end_block)

    def while_loop(self, tree: Tree):
        nodes = tree.children
        name = self.llvmgen.current_block.block.name

        (conditional_block, body_block, end_block) = self.llvmgen.create_loop(name,
                                                                              self.llvmgen.current_block)

        # Enter conditional block
        self.llvmgen.create_jump(conditional_block)
        self.llvmgen.enter_block(conditional_block)

        # Build condition
        condition: RIALVariable = self.transform_helper(nodes[0])
        self.llvmgen.create_conditional_jump(condition.raw_backing_value, body_block, end_block)

        # Go into body
        self.llvmgen.enter_block(body_block)

        # Build body
        i = 1
        while i < len(nodes):
            self.transform_helper(nodes[i])
            i += 1

        # Jump back into condition
        self.llvmgen.create_jump_if_not_exists(conditional_block)

        # Leave loop
        self.llvmgen.enter_block(end_block)

    def conditional_block(self, tree: Tree):
        nodes = tree.children

        name = self.llvmgen.current_block.block.name
        condition = nodes[0]
        likely_unlikely_modifier: Token = nodes[1]
        body = nodes[2]
        else_conditional: Optional[Tree] = len(nodes) > 3 and nodes[3] or None
        else_likely_unlikely_modifier = Token('STANDARD_WEIGHT', 50)

        if else_conditional is not None:
            if else_conditional.data == "conditional_else_block":
                else_likely_unlikely_modifier = else_conditional.children[0]
                else_conditional.children.pop(0)
            else:
                # Else-If
                # If the IF Condition is likely, then the else if is automatically unlikely
                # If the IF Condition is unlikely, then the else if is automatically likely
                # This is done because the last ELSE is the opposite of the first IF and thus the ELSE IFs are automatically gone through to get there.
                # The original ELSE IF weight is used in the following conditional blocks (that were inserted in this generated ELSE block).
                if likely_unlikely_modifier.type == "LIKELY":
                    else_likely_unlikely_modifier = Token("UNLIKELY", 10)
                else:
                    else_likely_unlikely_modifier = Token("LIKELY", 100)

        else_block = None

        if else_conditional is None:
            (conditional_block, body_block, end_block) = \
                self.llvmgen.create_conditional_block(name, self.llvmgen.current_block)
        else:
            (conditional_block, body_block, else_block, end_block) = \
                self.llvmgen.create_conditional_block_with_else(name,
                                                                self.llvmgen.current_block)

        if likely_unlikely_modifier.type == else_likely_unlikely_modifier.type and likely_unlikely_modifier.type != "STANDARD_WEIGHT":
            log_warn(
                f"{ParserState.module().filename}[{likely_unlikely_modifier.line}:{likely_unlikely_modifier.column}]WARNING 002")
            log_warn(f"Specifying the same weight on both conditionals cancels them out.")
            log_warn(f"Both can be safely removed.")

        # Create condition
        self.llvmgen.create_jump(conditional_block)
        self.llvmgen.enter_block(conditional_block)
        cond: RIALVariable = self.transform_helper(condition)

        self.llvmgen.create_conditional_jump(cond.raw_backing_value, body_block,
                                             else_block is not None and else_block or end_block,
                                             likely_unlikely_modifier.value, else_likely_unlikely_modifier.value)

        # Create body
        self.llvmgen.enter_block(body_block)

        for node in body.children:
            self.transform_helper(node)

        # Jump out of body
        self.llvmgen.create_jump_if_not_exists(end_block)

        # Create else if necessary
        if len(nodes) > 3:
            self.llvmgen.enter_block(else_block)
            for node in else_conditional.children:
                self.transform_helper(node)
            self.llvmgen.create_jump_if_not_exists(end_block)

        # Leave conditional block
        self.llvmgen.enter_block(end_block)

    def shorthand_if(self, tree: Tree):
        nodes = tree.children
        name = self.llvmgen.current_block.block.name
        (conditional_block, body_block, else_block, end_block) = \
            self.llvmgen.create_conditional_block_with_else(name, self.llvmgen.current_block)

        # Create condition
        self.llvmgen.create_jump(conditional_block)
        self.llvmgen.enter_block(conditional_block)
        cond: RIALVariable = self.transform_helper(nodes[0])
        self.llvmgen.create_conditional_jump(cond.raw_backing_value, body_block, else_block)

        # Create body
        self.llvmgen.enter_block(body_block)
        true_value: RIALVariable = self.transform_helper(nodes[1])

        # Jump out of body
        self.llvmgen.create_jump_if_not_exists(end_block)

        # Create else
        self.llvmgen.enter_block(else_block)
        false_value: RIALVariable = self.transform_helper(nodes[2])

        # Jump out of else
        self.llvmgen.create_jump_if_not_exists(end_block)

        # Leave conditional block
        self.llvmgen.enter_block(end_block)

        # PHI the values
        phi = self.llvmgen.builder.phi(true_value.llvm_type)
        phi.add_incoming(true_value.backing_value, body_block.block)
        phi.add_incoming(false_value.backing_value, else_block.block)

        return RIALVariable("phi", true_value.rial_type, phi)

    def switch_block(self, tree: Tree):
        nodes = tree.children
        parent = self.llvmgen.current_block
        variable: RIALVariable = self.transform_helper(nodes[0])
        end_block = self.llvmgen.create_block(f"{self.llvmgen.current_block.block.name}.end_switch",
                                              sibling=self.llvmgen.current_block)
        self.llvmgen.end_block = end_block
        switch = self.llvmgen.builder.switch(variable.raw_backing_value, None)
        collected_empties = list()

        i = 1
        while i < len(nodes):
            var, block = self.transform_helper(nodes[i])

            # Check if just case, collect for future use
            if block is None:
                collected_empties.append(var)
            else:
                self.llvmgen.enter_block_end(block)

                # Check if default case and set as default
                if var is None:
                    if switch.default is not None:
                        log_fail(f"{ParserState.module().name} Duplicate default case in switch statement")
                    else:
                        switch.default = block.block
                else:
                    switch.add_case(var, block.block)

                # Add all collected cases
                for collected_empty in collected_empties:
                    switch.add_case(collected_empty, block.block)

                collected_empties.clear()

            self.llvmgen.enter_block_end(parent)

            i += 1

        if switch.default is None:
            switch.default = end_block.block

        if len(collected_empties) > 0:
            log_fail("Empty cases in switch statement!")

        self.llvmgen.end_block = None
        self.llvmgen.enter_block(end_block)

    def switch_case(self, tree: Tree):
        nodes = tree.children
        var: RIALVariable = self.transform_helper(nodes[0])

        # We need to load here as we are still in the parent's block and not the conditional block
        var = var.raw_backing_value

        if len(nodes) == 1:
            return var, None
        block = self.llvmgen.create_block(f"{self.llvmgen.current_block.block.name}.switch.case",
                                          self.llvmgen.current_block)
        self.llvmgen.enter_block(block)

        i = 1
        while i < len(nodes):
            self.transform_helper(nodes[i])
            i += 1

        self.llvmgen.finish_current_block()

        return var, block

    def default_case(self, tree: Tree):
        nodes = tree.children
        block = self.llvmgen.create_block(f"{self.llvmgen.current_block.block.name}.switch.default",
                                          self.llvmgen.current_block)
        self.llvmgen.enter_block(block)
        for node in nodes:
            self.transform_helper(node)

        self.llvmgen.finish_current_block()

        return None, block

    def unsafe_block(self, tree: Tree):
        nodes = tree.children
        self.llvmgen.currently_unsafe = True
        i = 1
        while i < len(nodes):
            self.visit(nodes[i])
            i += 1

    def struct_decl(self, tree: Tree):
        nodes = tree.children
        node = nodes[0]
        full_name = node.metadata['struct_name']
        function_decls = node.metadata['functions']

        struct = ParserState.search_structs(full_name)

        if struct is None:
            raise KeyError(f"Expected a struct {full_name} but couldn't find it!")

        self.llvmgen.current_struct = struct

        # Create functions
        for function_decl in function_decls:
            self.visit(function_decl)

        self.llvmgen.finish_struct()

    def constructor_call(self, tree: Tree):
        nodes = tree.children
        name = nodes[0]
        struct = ParserState.find_struct(name)

        if struct is None:
            log_fail(f"Instantiation of unknown type {name}")

        arguments = list()

        instantiated = self.llvmgen.builder.alloca(struct)
        instantiated = RIALVariable(name, name, instantiated)
        arguments.append(instantiated)

        arguments.extend(self.transform_helper(nodes[1]))
        llvm_args = [arg.backing_value for arg in arguments]

        constructor_name = mangle_function_name("constructor", [arg.llvm_type for arg in arguments], name)

        try:
            call_instr = self.llvmgen.gen_function_call([constructor_name], llvm_args)

            if call_instr is None:
                log_fail(f"Failed to generate call to function {constructor_name}")
                return NULL

            return instantiated
        except IndexError:
            log_fail("Missing argument in function call")

        return NULL

    def nested_function_call(self, tree: Tree):
        nodes = tree.children
        i = 0
        full_name = ""
        arguments = list()
        while i < len(nodes):
            if not isinstance(nodes[i], Token):
                break

            full_name += f".{nodes[i].value}"
            i += 1

        implicit_parameter_name = '.'.join(full_name.split('.')[0:-1])
        function_name = full_name.split('.')[-1]
        implicit_parameter: RIALVariable = self.llvmgen.get_definition(implicit_parameter_name)

        if implicit_parameter is None:
            log_fail(f"Could not find implicit parameter {implicit_parameter_name} in function call {full_name}")
            return NULL

        arguments.append(implicit_parameter)
        arguments.extend(self.transform_helper(nodes[i]))

        arg_types = [arg.llvm_type for arg in arguments]
        mangled_names = list()

        # Generate mangled names for implicit parameter and derived
        if implicit_parameter is not None:
            ty = implicit_parameter.rial_type

            # Check if it's a builtin type
            if ty in ParserState.builtin_types:
                mangled_names.append(mangle_function_name(function_name, arg_types, ty))
            else:
                mangled_names.append(mangle_function_name(function_name, arg_types, ty))

                struct = ParserState.find_struct(ty)

                # Also mangle base structs to see if it's a derived function
                for base_struct in struct.definition.base_structs:
                    arg_tys = arg_types
                    arg_tys.pop(0)
                    arg_tys.insert(0, base_struct)
                    mangled_names.append(
                        mangle_function_name(function_name, arg_types, base_struct))
        else:
            mangled_names.append(mangle_function_name(function_name, arg_types))

        try:
            call_instr = self.llvmgen.gen_function_call([*mangled_names, function_name],
                                                        [arg.backing_value for arg in arguments])

            if call_instr is None:
                log_fail(f"Failed to generate call to function {function_name}")
                return NULL

            rial_func = call_instr.callee

            if isinstance(rial_func, RIALFunction):
                return RIALVariable(f"{rial_func.name}_call", rial_func.definition.rial_return_type, call_instr)
            return RIALVariable(f"{rial_func.name}_call", "Unknown", call_instr)
        except IndexError:
            log_fail(f"Missing argument in function call to function {function_name}")

        return NULL

    def function_call(self, tree: Tree):
        nodes = tree.children
        full_function_name: str
        function_name: str

        # Function call specialisation
        if isinstance(nodes[0], Tree):
            return self.visit(nodes[0])

        function_name = nodes[0].value
        arguments: List[RIALVariable] = self.transform_helper(nodes[1])

        arg_types = [arg.llvm_type for arg in arguments]

        try:
            call_instr = self.llvmgen.gen_function_call([mangle_function_name(function_name, arg_types), function_name],
                                                        [arg.backing_value for arg in arguments])

            if call_instr is None:
                log_fail(f"Failed to generate call to function {function_name}")
                return NULL

            rial_func = call_instr.callee

            if isinstance(rial_func, RIALFunction):
                return RIALVariable(f"{rial_func.name}_call", rial_func.definition.rial_return_type, call_instr)
            return RIALVariable(f"{rial_func.name}_call", "Unknown", call_instr)
        except IndexError:
            log_fail("Missing argument in function call")

        return NULL

    def function_args(self, tree: Tree):
        nodes = tree.children
        arguments = list()
        for node in nodes:
            arguments.append(self.transform_helper(node))

        return arguments

    def function_decl(self, tree: Tree):
        nodes = tree.children

        node: MetadataToken = nodes[0]
        body_start = node.metadata['body_start']
        func: RIALFunction = node.metadata['func']

        if func is None:
            raise KeyError("Expected a function but didn't find it!")

        self.llvmgen.create_function_body(func, [arg.rial_type for arg in func.definition.rial_args])
        old_unsafe = self.llvmgen.currently_unsafe

        # Only set unsafely if the current context is safe.
        if not old_unsafe:
            self.llvmgen.currently_unsafe = func.definition.unsafe

        i = body_start
        while i < len(nodes):
            self.transform_helper(nodes[i])
            i += 1

        self.llvmgen.finish_current_block()
        self.llvmgen.finish_current_func()
        self.llvmgen.currently_unsafe = old_unsafe

        return None
