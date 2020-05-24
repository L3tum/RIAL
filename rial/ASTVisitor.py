from typing import Optional, List

from llvmlite import ir
from llvmlite.ir import BaseStructType, GEPInstr

from rial.LLVMBlock import LLVMBlock
from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import map_llvm_to_type, NULL, Int32, is_array, map_shortcut_to_type
from rial.compilation_manager import CompilationManager
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.concept.parser import Interpreter, Tree, Token, Discard
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

    def sizeof(self, tree: Tree):
        nodes = tree.children
        variable: RIALVariable = self.transform_helper(nodes[0])
        sloc = None

        # It's a type and not a variable
        if variable is None:
            name = nodes[0].children[0].value
            ty = ParserState.map_type_to_llvm_no_pointer(name)

            size = Int32(CompilationManager.codegen.get_size(ty))
        elif variable.is_pointer:
            if is_array(variable.rial_type):
                arr_type: ir.ArrayType = variable.pointee_type
                size = CompilationManager.codegen.get_size(arr_type.element)
                size = arr_type.count * size

                size = Int32(size)
            else:
                ty: ir.Type = variable.pointee_type
                size = Int32(CompilationManager.codegen.get_size(ty))
        else:
            size = Int32(CompilationManager.codegen.get_size(variable.llvm_type))

        # This is worst case as it cannot be optimized away.
        # base = self.llvmgen.builder.ptrtoint(self.llvmgen.builder.gep(variable, [ir.Constant(ir.IntType(32), 0)]),
        #                                      ir.IntType(32))
        # val = self.llvmgen.builder.ptrtoint(self.llvmgen.builder.gep(variable, [ir.Constant(ir.IntType(32), 1)]),
        #                                     ir.IntType(32))
        # size = self.llvmgen.builder.sub(val, base)

        size = RIALVariable("tmp", "Int32", size, sloc=sloc)

        return size

    def array_constructor(self, tree: Tree):
        nodes = tree.children
        name = nodes[0].value
        number: RIALVariable = self.transform_helper(nodes[1])
        number = number.value_for_calculations

        if isinstance(number, ir.Constant):
            number = number.constant

        ty = ParserState.map_type_to_llvm_no_pointer(name)
        arr_type = ir.ArrayType(ty, number)
        array = self.llvmgen.builder.alloca(arr_type)

        return RIALVariable(f"{name}_arr", map_shortcut_to_type(name), array, sloc=(nodes[0].line, nodes[0].column))

    def array_assignment(self, tree: Tree):
        nodes = tree.children
        array: RIALVariable = self.transform_helper(nodes[0].children[0])
        index: RIALVariable = self.transform_helper(nodes[0].children[1])
        val: RIALVariable = self.transform_helper(nodes[2])
        entry = self.llvmgen.builder.gep(array, [Int32(0), index.value_for_calculations])
        self.llvmgen.builder.store(val.value_for_calculations, entry)

        # We return val here in order to support chained assignment (though I'm not sure if we do nor will).
        return val

    def array_access(self, tree: Tree):
        nodes = tree.children
        variable: RIALVariable = self.transform_helper(nodes[0])

        index: RIALVariable = self.transform_helper(nodes[1])

        var = self.llvmgen.builder.gep(variable.backing_value, [Int32(0), index.value_for_calculations])

        return RIALVariable("tmp", variable.rial_type_of_array_element, var, sloc=index.sloc)

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

        variable = self.llvmgen.get_definition(identifier)

        if variable is None:
            return None

        if isinstance(variable, RIALVariable):
            return variable

        sloc = (token.line, token.column)

        if isinstance(variable, RIALFunction):
            ptr = self.llvmgen.builder.alloca(ir.PointerType(variable.function_type))
            self.llvmgen.builder.store(variable, ptr)
            return RIALVariable(f"{variable.name}_ptr", "Function", ptr, sloc=sloc)
        elif isinstance(variable, GEPInstr):
            return RIALVariable("tmp", map_llvm_to_type(variable.type.pointee), variable,
                                sloc=sloc)
        else:
            return RIALVariable("tmp", map_llvm_to_type(variable.type.pointee), variable,
                                sloc=sloc)

    def comparison(self, tree: Tree):
        nodes = tree.children
        left: RIALVariable = self.transform_helper(nodes[0])
        comparison = nodes[1].value
        right: RIALVariable = self.transform_helper(nodes[2])

        if left.rial_type != right.rial_type:
            raise TypeError(left, right)

        # If both are pointers, we need to compare the pointers to see if they're the same.
        # If one of them isn't a pointer, we need to get the value used for calculations to see if they're the same.
        # Special case is if both point to primitives, which would mean we'd need to load both of them to compare them.
        pointers = left.is_pointer and right.is_pointer
        left_val = (pointers and not left.points_to_primitive) and left.backing_value or left.value_for_calculations
        right_val = (pointers and not right.points_to_primitive) and right.backing_value or right.value_for_calculations

        comp = self.llvmgen.gen_comparison(comparison, left_val, right_val)

        if comp is None:
            raise TypeError(f"Could not create comparison of type '{comparison}'")

        rial_type = map_llvm_to_type(comp.type)
        var = self.llvmgen.declare_nameless_variable_from_rial_type(rial_type, comp)
        variable = RIALVariable("tmp", rial_type, var, sloc=(nodes[1].line, nodes[1].column))
        return variable

    def math(self, tree: Tree):
        nodes = tree.children

        left: RIALVariable = self.transform_helper(nodes[0])
        right: RIALVariable = self.transform_helper(nodes[2])

        if left.rial_type != right.rial_type:
            raise TypeError(left, right)

        left_val = left.value_for_calculations
        right_val = right.value_for_calculations

        op = nodes[1].type
        result = None

        if op == "PLUS":
            result = self.llvmgen.gen_addition(left_val, right_val)
        elif op == "MINUS":
            result = self.llvmgen.gen_subtraction(left_val, right_val)
        elif op == "MUL":
            result = self.llvmgen.gen_multiplication(left_val, right_val)
        elif op == "DIV":
            result = self.llvmgen.gen_division(left_val, right_val)

        return RIALVariable("tmp", left.rial_type, result, sloc=(nodes[1].line, nodes[1].column))

    def variable_assignment(self, tree: Tree):
        nodes = tree.children

        variable: RIALVariable = self.transform_helper(nodes[0])
        value: RIALVariable = self.transform_helper(nodes[2])

        if variable.rial_type != value.rial_type:
            raise TypeError(str(variable), str(value))

        if variable.is_allocated_variable and value.is_allocated_variable:
            value.name = variable.name
            value.backing_value.name = variable.backing_value.name
            self.llvmgen.current_block.add_named_value(variable.name, value)
        else:
            self.llvmgen.builder.store(value.value_for_calculations, variable.backing_value)

        # Return value to support chained assignment
        return value

    def global_variable_assignment(self, tree: Tree):
        nodes = tree.children[0].children

        with self.llvmgen.create_in_global_ctor():
            variable = self.transform_helper(nodes[0])
            value = self.transform_helper(nodes[2])

            if variable.rial_type != value.rial_type:
                raise TypeError(variable, value)

            if variable.is_allocated_variable and value.is_allocated_variable:
                value.name = variable.name
                value.backing_value.name = variable.backing_value.name
            else:
                self.llvmgen.builder.store(value.value_for_calculations, variable.backing_value)
        return value

    def variable_decl(self, tree: Tree):
        nodes = tree.children
        identifier: str = nodes[0].value
        value: RIALVariable = self.transform_helper(nodes[2])

        if value.is_allocated_variable:
            value.backing_value.name = identifier
            variable = value
        else:
            variable = self.llvmgen.builder.alloca(value.llvm_type, name=identifier)
            self.llvmgen.builder.store(value.value_for_assignment, variable)
            variable = RIALVariable(identifier, value.rial_type, variable, sloc=(nodes[0].line, nodes[0].column))

        self.llvmgen.current_block.add_named_value(identifier, variable)

        return value

    def cast(self, tree: Tree):
        nodes = tree.children
        ty = ParserState.map_type_to_llvm_no_pointer(nodes[0])
        value: RIALVariable = self.transform_helper(nodes[1])
        sloc = (nodes[0].line, nodes[0].column)
        cast = None

        if isinstance(ty, BaseStructType) and value.value_is_integer:
            if not self.llvmgen.currently_unsafe:
                raise PermissionError("Cannot cast integer to pointer in a safe context")
            cast = self.llvmgen.builder.inttoptr(value.value_for_calculations, ty.as_pointer())
        elif isinstance(ty, BaseStructType):
            cast = self.llvmgen.builder.bitcast(value.backing_value, ty.as_pointer())
        else:
            cast_function = get_casting_function(value.llvm_type, ty)

            if hasattr(self.llvmgen.builder, cast_function):
                cast = getattr(self.llvmgen.builder, cast_function)(value.value_for_calculations, ty)

        if cast is not None:
            return RIALVariable("cast", map_llvm_to_type(ty), cast, sloc=sloc)

        log_fail(f"Invalid cast from {value.rial_type} to {nodes[0]}")

        raise Discard()

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

        return_val: RIALVariable = self.transform_helper(nodes[0])
        return_val = self.llvmgen.create_return_statement(return_val)

        return return_val

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
        self.llvmgen.create_conditional_jump(condition.value_for_calculations, body_block, end_block)

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
        self.llvmgen.create_conditional_jump(condition.value_for_calculations, body_block, end_block)

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

        self.llvmgen.create_conditional_jump(cond.value_for_calculations, body_block,
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
        self.llvmgen.create_conditional_jump(cond.value_for_calculations, body_block, else_block)

        # Create body
        self.llvmgen.enter_block(body_block)
        true_value: RIALVariable = self.transform_helper(nodes[1])

        # Jump out of body
        self.llvmgen.create_jump_if_not_exists(end_block)

        # Create else
        self.llvmgen.enter_block(else_block)
        false_value: RIALVariable = self.transform_helper(nodes[2])
        self.llvmgen.create_jump_if_not_exists(end_block)

        # Leave conditional block
        self.llvmgen.enter_block(end_block)

        # PHI the values
        phi = self.llvmgen.builder.phi(true_value.llvm_type)
        phi.add_incoming(true_value.backing_value, body_block.block)
        phi.add_incoming(false_value.backing_value, else_block.block)

        phi_variable = RIALVariable("phi", true_value.rial_type, phi)

        return phi_variable

    def switch_block(self, tree: Tree):
        nodes = tree.children
        parent = self.llvmgen.current_block
        variable: RIALVariable = self.transform_helper(nodes[0])
        end_block = self.llvmgen.create_block(f"{self.llvmgen.current_block.block.name}.end_switch",
                                              sibling=self.llvmgen.current_block)
        self.llvmgen.end_block = end_block
        switch = self.llvmgen.builder.switch(variable.value_for_calculations, None)
        collected_empties = list()

        i = 1
        while i < len(nodes):
            var, block = self.transform_helper(nodes[i])
            block: LLVMBlock

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

        # Why do this, you ask? Well, the load needs to happen in the parent block (which we are in right now),
        # rather than the conditional block (which we'd be in if we'd do it in the switch_block function).
        var = var.value_for_calculations

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
            self.transform_helper(nodes[i])
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
            self.transform_helper(function_decl)

        self.llvmgen.finish_struct()

    def constructor_call(self, tree: Tree):
        nodes = tree.children
        name = nodes[0]
        struct = ParserState.find_struct(name)

        if struct is None:
            log_fail(f"Instantiation of unknown type {name}")

        arguments: List[RIALVariable] = list()

        instantiated = self.llvmgen.builder.alloca(struct)
        instantiated = RIALVariable(f"{name}_inst", struct.name, instantiated, sloc=(nodes[0].line, nodes[0].column))
        arguments.append(instantiated)

        arguments.extend(self.transform_helper(nodes[1]))

        constructor_name = mangle_function_name("constructor", [arg.llvm_type_as_function_arg for arg in arguments],
                                                name)

        try:
            call_instr = self.llvmgen.gen_function_call([constructor_name], arguments)

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
        name_nodes: List[Token] = list()
        while i < len(nodes):
            if not isinstance(nodes[i], Token):
                break

            name_nodes.append(nodes[i])
            i += 1

        function_name = name_nodes[-1].value
        implicit_parameter_nodes = name_nodes[0:-1]
        implicit_parameter_name = '.'.join(implicit_parameter_nodes)
        implicit_parameter: RIALVariable = self.var(Tree('var', implicit_parameter_nodes))

        if implicit_parameter is None:
            log_fail(f"Could not find implicit parameter {implicit_parameter_name} in function call {function_name}")
            return NULL

        arguments: List[RIALVariable] = list()
        arguments.append(implicit_parameter)
        arguments.extend(self.transform_helper(nodes[i]))

        mangled_names = list()
        # Generate mangled names for implicit parameter and derived
        if implicit_parameter is not None:
            mangled_names.append(
                mangle_function_name(function_name, [arg.llvm_type_as_function_arg for arg in arguments],
                                     implicit_parameter.llvm_type.name))

            # TODO: Base function finding
            # struct = implicit_parameter.llvm_type
            #
            #
            # # Also mangle base structs to see if it's a derived function
            # for base_struct in struct.definition.base_structs:
            #     arg_tys = arguments
            #     arg_tys.pop(0)
            #     arg_tys.insert(0, base_struct)
            #     mangled_names.append(
            #         mangle_function_name(function_name, arg_types, base_struct))
        else:
            mangled_names.append(
                mangle_function_name(function_name, [arg.llvm_type_as_function_arg for arg in arguments]))

        try:
            call_instr = self.llvmgen.gen_function_call([*mangled_names, function_name], arguments)

            if call_instr is None:
                log_fail(f"Failed to generate call to function {function_name}")
                return NULL

            rial_func = call_instr.callee

            # Check if function called is an actual function and not a variable pointing to a function
            if isinstance(rial_func, RIALFunction):
                return RIALVariable(f"{rial_func.name}_call", rial_func.definition.rial_return_type, call_instr,
                                    sloc=(nodes[0].line, nodes[0].column))
            if isinstance(rial_func.type, ir.FunctionType):
                return RIALVariable(f"{rial_func.name}_call", map_llvm_to_type(rial_func.type.return_type),
                                    call_instr,
                                    sloc=(nodes[0].line, nodes[0].column))
            if isinstance(rial_func.type, ir.PointerType):
                return RIALVariable(f"{rial_func.name}_call", map_llvm_to_type(rial_func.type.pointee.return_type),
                                    call_instr,
                                    sloc=(nodes[0].line, nodes[0].column))

            return RIALVariable(f"{rial_func.name}_call", map_llvm_to_type(rial_func.type.return_type),
                                call_instr,
                                sloc=(nodes[0].line, nodes[0].column))
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

        try:
            call_instr = self.llvmgen.gen_function_call(
                [mangle_function_name(function_name, [arg.llvm_type_as_function_arg for arg in arguments]),
                 function_name],
                arguments)

            if call_instr is None:
                log_fail(f"Failed to generate call to function {function_name}")
                print([str(arg) for arg in arguments])
                return NULL

            rial_func = call_instr.callee

            if isinstance(rial_func, RIALFunction):
                return RIALVariable(f"{rial_func.name}_call", rial_func.definition.rial_return_type, call_instr,
                                    sloc=(nodes[0].line, nodes[0].column))
            if isinstance(rial_func.type, ir.FunctionType):
                return RIALVariable(f"{rial_func.name}_call", map_llvm_to_type(rial_func.type.return_type),
                                    call_instr,
                                    sloc=(nodes[0].line, nodes[0].column))
            if isinstance(rial_func.type, ir.PointerType):
                return RIALVariable(f"{rial_func.name}_call", map_llvm_to_type(rial_func.type.pointee.return_type),
                                    call_instr,
                                    sloc=(nodes[0].line, nodes[0].column))

            return RIALVariable(f"{rial_func.name}_call", map_llvm_to_type(rial_func.type.return_type),
                                call_instr,
                                sloc=(nodes[0].line, nodes[0].column))
        except IndexError:
            log_fail(f"Missing argument in function call to function {function_name}")
            log_fail(f"Arguments: {', '.join([arg.name for arg in arguments])}")

        return NULL

    def function_args(self, tree: Tree):
        nodes = tree.children
        arguments: List[RIALVariable] = list()
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
