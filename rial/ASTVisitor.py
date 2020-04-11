from typing import Tuple, List, Optional

import os
from llvmlite import ir
from llvmlite.ir import PointerType, IdentifiedStructType, IRBuilder

from rial.LLVMBlock import create_llvm_block
from rial.LLVMFunction import LLVMFunction
from rial.SingleParserState import SingleParserState
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.log import log_fail
from rial.concept.parser import Interpreter, Tree, Token, v_args, Meta
from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class ASTVisitor(Interpreter):
    sps: SingleParserState

    def __init__(self, sps: SingleParserState):
        self.sps = sps

    def transform_helper(self, node):
        if isinstance(node, Tree):
            return self.visit(node)

        return node

    def load_nested(self, val, name: str):
        if isinstance(val.type, PointerType):
            if isinstance(val.type.pointee, IdentifiedStructType):
                llvm_struct = self.find_struct(val.type.pointee.name)

                if llvm_struct is None:
                    return None

                prop = llvm_struct.properties[name]

                if prop is None:
                    return None

                return self.sps.llvmgen.builder.gep(val,
                                                    [ir.Constant(ir.IntType(32), prop[0]),
                                                     ir.Constant(ir.IntType(32), 0)])

        return val

    def addition(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.sps.llvmgen.gen_addition(left, right)

    def subtraction(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.sps.llvmgen.gen_subtraction(left, right)

    def multiplication(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.sps.llvmgen.gen_multiplication(left, right)

    def division(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.sps.llvmgen.gen_division(left, right)

    def smaller_than(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.sps.llvmgen.gen_comparison('<', left, right)

    def bigger_than(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.sps.llvmgen.gen_comparison('>', left, right)

    def bigger_equal(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.sps.llvmgen.gen_comparison('>=', left, right)

    def smaller_equal(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.sps.llvmgen.gen_comparison('<=', left, right)

    def get_var(self, identifier: str):
        variable = self.sps.llvmgen.current_block.get_named_value(identifier)

        if variable is None:
            log_fail(f"Variable not found {identifier}")
            return None

        return variable

    def var(self, tree: Tree):
        nodes = tree.children

        va = self.get_var(nodes[0].value)

        if isinstance(va.type, PointerType):
            return self.sps.llvmgen.builder.load(va)

        return va

    def variable_increment(self, tree: Tree):
        nodes = tree.children
        variable = self.get_var(nodes[0].value)

        if len(nodes) > 1:
            value = self.transform_helper(nodes[1])
        else:
            variable_type = variable.type

            if isinstance(variable_type, PointerType):
                variable_type = variable_type.pointee

            value = ir.Constant(variable_type, 1)

        return self.sps.llvmgen.gen_shorthand(variable, value, '+')

    def variable_decrement(self, tree: Tree):
        nodes = tree.children
        variable = self.get_var(nodes[0].value)

        if len(nodes) > 1:
            value = self.transform_helper(nodes[1])
        else:
            variable_type = variable.type

            if isinstance(variable_type, PointerType):
                variable_type = variable_type.pointee

            value = ir.Constant(variable_type, 1)

        return self.sps.llvmgen.gen_shorthand(variable, value, '-')

    def variable_multiplication(self, tree: Tree):
        nodes = tree.children
        variable = self.get_var(nodes[0].value)
        value = self.transform_helper(nodes[1])

        return self.sps.llvmgen.gen_shorthand(variable, value, '*')

    def variable_division(self, tree: Tree):
        nodes = tree.children
        variable = self.get_var(nodes[0].value)
        value = self.transform_helper(nodes[1])

        return self.sps.llvmgen.gen_shorthand(variable, value, '/')

    def variable_assignment(self, tree: Tree):
        nodes = tree.children
        identifier = nodes[0].value
        value = self.transform_helper(nodes[1])

        # TODO: Check if types are matching based on both LLVM value and inferred and metadata RIAL type
        return self.sps.llvmgen.assign_to_variable(identifier, value)

    def variable_decl(self, tree: Tree):
        nodes = tree.children
        identifier = nodes[0].value
        value = self.transform_helper(nodes[1])
        value_type = value.type

        # TODO: Infer type based on value, essentially map LLVM type to RIAL type
        return self.sps.llvmgen.declare_variable(identifier, value_type, value, "")

    def continue_rule(self, tree: Tree):
        if self.sps.llvmgen.conditional_block is None:
            log_fail(f"'continue' outside of loop")
            return None

        return self.sps.llvmgen.create_jump(self.sps.llvmgen.conditional_block)

    def break_rule(self, tree: Tree):
        if self.sps.llvmgen.end_block is None:
            log_fail(f"'break' outside of loop or conditional block")
            return None

        return self.sps.llvmgen.create_jump(self.sps.llvmgen.end_block)

    def return_rule(self, tree: Tree):
        nodes = tree.children

        if self.sps.llvmgen.current_block.block.terminator is not None:
            log_fail(f"'return' after return found!")
            return None

        return self.sps.llvmgen.create_return_statement(self.transform_helper(nodes[0]))

    def loop_loop(self, tree: Tree):
        nodes = tree.children
        name = self.sps.llvmgen.current_block.block.name

        (conditional_block, body_block, end_block) = self.sps.llvmgen.create_loop(name, self.sps.llvmgen.current_block)

        # Remove conditional block again (there's no condition)
        self.sps.llvmgen.current_func.basic_blocks.remove(conditional_block.block)
        self.sps.llvmgen.conditional_block = body_block
        del conditional_block

        # Go into body
        self.sps.llvmgen.create_jump(body_block)
        self.sps.llvmgen.enter_block(body_block)

        # Build body
        for node in nodes:
            self.transform_helper(node)

        # Jump back into body
        self.sps.llvmgen.create_jump_if_not_exists(body_block)

        # Go out of loop
        self.sps.llvmgen.enter_block(end_block)

    def for_loop(self, tree: Tree):
        nodes = tree.children
        name = self.sps.llvmgen.current_block.block.name
        name = f"{name}.wrapper"

        wrapper_block = self.sps.llvmgen.create_block(name, parent=self.sps.llvmgen.current_block)
        (conditional_block, body_block, end_block) = self.sps.llvmgen.create_loop(name, wrapper_block)

        # Move end_block out of wrapper block
        end_block.sibling = self.sps.llvmgen.current_block

        # Create variable in wrapper block
        self.sps.llvmgen.create_jump(wrapper_block)
        self.sps.llvmgen.enter_block(wrapper_block)
        self.transform_helper(nodes[0])

        # Enter conditional block
        self.sps.llvmgen.create_jump(conditional_block)
        self.sps.llvmgen.enter_block(conditional_block)

        # Build condition
        condition = self.transform_helper(nodes[1])
        self.sps.llvmgen.create_conditional_jump(condition, body_block, end_block)

        # Go into body
        self.sps.llvmgen.enter_block(body_block)

        # Build body
        i = 3
        while i < len(nodes):
            self.transform_helper(nodes[i])
            i += 1

        # Build incrementor if no terminator yet
        if self.sps.llvmgen.current_block.block.terminator is None:
            self.transform_helper(nodes[2])

        # Jump back into condition
        self.sps.llvmgen.create_jump_if_not_exists(conditional_block)

        # Go out of loop
        self.sps.llvmgen.enter_block(end_block)

    def while_loop(self, tree: Tree):
        nodes = tree.children
        name = self.sps.llvmgen.current_block.block.name

        (conditional_block, body_block, end_block) = self.sps.llvmgen.create_loop(name, self.sps.llvmgen.current_block)

        # Enter conditional block
        self.sps.llvmgen.create_jump(conditional_block)
        self.sps.llvmgen.enter_block(conditional_block)

        # Build condition
        condition = self.transform_helper(nodes[0])
        self.sps.llvmgen.create_conditional_jump(condition, body_block, end_block)

        # Go into body
        self.sps.llvmgen.enter_block(body_block)

        # Build body
        i = 1
        while i < len(nodes):
            self.transform_helper(nodes[i])
            i += 1

        # Jump back into condition
        self.sps.llvmgen.create_jump_if_not_exists(conditional_block)

        # Leave loop
        self.sps.llvmgen.enter_block(end_block)

    def conditional_block(self, tree: Tree):
        nodes = tree.children
        name = self.sps.llvmgen.current_block.block.name
        else_block = None

        if len(nodes) == 2:
            (conditional_block, body_block, end_block) = \
                self.sps.llvmgen.create_conditional_block(name, self.sps.llvmgen.current_block)
        else:
            (conditional_block, body_block, else_block, end_block) = \
                self.sps.llvmgen.create_conditional_block_with_else(name, self.sps.llvmgen.current_block)

        # Create condition
        self.sps.llvmgen.create_jump(conditional_block)
        self.sps.llvmgen.enter_block(conditional_block)
        cond = self.transform_helper(nodes[0])
        self.sps.llvmgen.create_conditional_jump(cond, body_block, end_block)

        # Create body
        self.sps.llvmgen.enter_block(body_block)
        self.transform_helper(nodes[1])

        # Jump out of body
        self.sps.llvmgen.create_jump_if_not_exists(end_block)

        # Create else if necessary
        if len(nodes) > 2:
            self.sps.llvmgen.enter_block(else_block)
            self.transform_helper(nodes[2])
            self.sps.llvmgen.create_jump_if_not_exists(end_block)

        # Leave conditional block
        self.sps.llvmgen.enter_block(end_block)

    def shorthand_if(self, tree: Tree):
        nodes = tree.children
        name = self.sps.llvmgen.current_block.block.name
        (conditional_block, body_block, else_block, end_block) = \
            self.sps.llvmgen.create_conditional_block_with_else(name, self.sps.llvmgen.current_block)

        # Create condition
        self.sps.llvmgen.create_jump(conditional_block)
        self.sps.llvmgen.enter_block(conditional_block)
        cond = self.transform_helper(nodes[0])
        self.sps.llvmgen.create_conditional_jump(cond, body_block, else_block)

        # Create body
        self.sps.llvmgen.enter_block(body_block)
        true_value = self.transform_helper(nodes[1])

        # Jump out of body
        self.sps.llvmgen.create_jump_if_not_exists(end_block)

        # Create else
        self.sps.llvmgen.enter_block(else_block)
        false_value = self.transform_helper(nodes[2])
        self.sps.llvmgen.create_jump_if_not_exists(end_block)

        # Leave conditional block
        self.sps.llvmgen.enter_block(end_block)

        # PHI the values
        phi = self.sps.llvmgen.builder.phi(true_value.type)
        phi.add_incoming(true_value, body_block.block)
        phi.add_incoming(false_value, else_block.block)

        return phi

    def struct_decl(self, tree: Tree):
        nodes = tree.children
        node = nodes[0]
        full_name = node.metadata['struct_name']
        function_decls = node.metadata['functions']

        llvm_struct = self.sps.ps.search_structs(full_name)

        if llvm_struct is None:
            raise KeyError("Expected a struct but couldn't find it!")

        self.sps.llvmgen.current_struct = llvm_struct

        # Create functions
        for function_decl in function_decls:
            self.visit(function_decl)

        self.sps.llvmgen.finish_struct()

    def function_call(self, tree: Tree):
        nodes = tree.children
        full_function_name: str
        start = 1
        implicit_parameter = None

        if len(nodes) > 1 and not isinstance(nodes[1], Tree) and nodes[1].type == "IDENTIFIER":
            full_function_name = nodes[1].value

            # Get initial value
            implicit_parameter = self.get_var(nodes[0].value)

            # Go along the nested properties to get to the function call
            for i, node in enumerate(nodes):
                # Skip first occurence since that is most likely the just-loaded variable
                if i == 0:
                    continue
                if not isinstance(node, Tree) and node.type == "IDENTIFIER":
                    # If next node is still identifier, we keep going
                    if len(nodes) > i + 1 and not isinstance(nodes[i + 1], Tree) and nodes[i + 1].type == "IDENTIFIER":
                        implicit_parameter = self.load_nested(implicit_parameter, node.value)
                    else:
                        start = i + 1
                        break
                else:
                    start = i
                    break

        else:
            full_function_name: str = nodes[0].value

        i = start
        arguments: list = list()

        if implicit_parameter is not None:
            arguments.append(implicit_parameter)

        while i < len(nodes):
            if nodes[i] is None:
                continue

            arguments.append(self.transform_helper(nodes[i]))
            i += 1

        mangled_name = mangle_function_name(full_function_name, [str(arg.type) for arg in arguments])
        func = self.sps.find_function(mangled_name)

        # Check if it's an external (aka not mangled call)
        if func is None:
            func = self.sps.find_function(full_function_name)
            # TODO: Should we get the LLVMFunction definition and actually check if it's external?

        # Check if it's actually an instantiation
        if func is None:
            llvm_struct = self.sps.find_struct(full_function_name)

            if llvm_struct is not None:
                func = llvm_struct.constructor
            else:
                log_fail(f"Undeclared function or constructor {full_function_name} called!")
                return None

        try:
            return self.sps.llvmgen.builder.call(func, arguments)
        except IndexError:
            log_fail("Missing argument in function call")

        return None

    def function_decl(self, tree: Tree):
        nodes = tree.children

        node: MetadataToken = nodes[0]
        body_start = node.metadata['body_start']
        function_name = node.metadata['full_name']
        rial_arg_types = node.metadata['rial_arg_types']
        func = next((func for func in self.sps.llvmgen.module.functions if func.name == function_name), None)

        if func is None:
            raise KeyError("Expected a function but didn't find it!")

        self.sps.llvmgen.create_function_body(func, rial_arg_types)

        i = body_start
        while i < len(nodes):
            self.transform_helper(nodes[i])
            i += 1

        self.sps.llvmgen.finish_current_block()

        return None
