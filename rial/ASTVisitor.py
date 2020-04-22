from llvmlite import ir
from llvmlite.ir import PointerType

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import map_llvm_to_type
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.concept.parser import Interpreter, Tree, Token
from rial.log import log_fail


class ASTVisitor(Interpreter):
    llvmgen: LLVMGen

    def __init__(self):
        super().__init__()
        self.llvmgen = LLVMGen()

    def transform_helper(self, node):
        if isinstance(node, Tree):
            node = self.visit(node)

        return node

    def addition(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_addition(left, right)

    def subtraction(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_subtraction(left, right)

    def multiplication(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_multiplication(left, right)

    def division(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_division(left, right)

    def smaller_than(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_comparison('<', left, right)

    def bigger_than(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_comparison('>', left, right)

    def bigger_equal(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_comparison('>=', left, right)

    def smaller_equal(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_comparison('<=', left, right)

    def equal(self, tree: Tree):
        nodes = tree.children
        left = self.transform_helper(nodes[0])
        right = self.transform_helper(nodes[2])

        return self.llvmgen.gen_comparison('==', left, right)

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

        va = self.llvmgen.get_var(identifier)

        if va is None:
            log_fail(f"{ParserState.module().name}[{token.line}:{token.column}] Error 0001")
            log_fail(f"Could not find identifier {identifier}")

        return va

    def variable_increment(self, tree: Tree):
        nodes = tree.children
        variable = self.var(nodes[0])

        if len(nodes) > 1:
            value = self.transform_helper(nodes[1])
        else:
            variable_type = variable.type

            if isinstance(variable_type, PointerType):
                variable_type = variable_type.pointee

            value = ir.Constant(variable_type, 1)

        return self.llvmgen.gen_shorthand(variable, value, '+')

    def variable_decrement(self, tree: Tree):
        nodes = tree.children
        variable = self.var(nodes[0])

        if len(nodes) > 1:
            value = self.transform_helper(nodes[1])
        else:
            variable_type = variable.type

            if isinstance(variable_type, PointerType):
                variable_type = variable_type.pointee

            value = ir.Constant(variable_type, 1)

        return self.llvmgen.gen_shorthand(variable, value, '-')

    def variable_multiplication(self, tree: Tree):
        nodes = tree.children
        variable = self.var(nodes[0])
        value = self.transform_helper(nodes[1])

        return self.llvmgen.gen_shorthand(variable, value, '*')

    def variable_division(self, tree: Tree):
        nodes = tree.children
        variable = self.var(nodes[0])
        value = self.transform_helper(nodes[1])

        return self.llvmgen.gen_shorthand(variable, value, '/')

    def variable_assignment(self, tree: Tree):
        nodes = tree.children

        variable = self.var(nodes[0])
        value = self.transform_helper(nodes[2])

        # TODO: Check if types are matching based on both LLVM value and inferred and metadata RIAL type
        return self.llvmgen.assign_to_variable(variable, value)

    def variable_decl(self, tree: Tree):
        nodes = tree.children
        identifier = nodes[0].value
        value = self.transform_helper(nodes[2])
        value_type = value.type

        return self.llvmgen.declare_variable(identifier, value_type, value, map_llvm_to_type(value_type))

    def global_variable_decl(self, tree: Tree):
        # nodes = tree.children
        # print(nodes)
        pass

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

        return_val = self.llvmgen.create_return_statement(self.transform_helper(nodes[0]))

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
        condition = self.transform_helper(nodes[1])
        self.llvmgen.create_conditional_jump(condition, body_block, end_block)

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
        condition = self.transform_helper(nodes[0])
        self.llvmgen.create_conditional_jump(condition, body_block, end_block)

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
        else_block = None

        if len(nodes) == 2:
            (conditional_block, body_block, end_block) = \
                self.llvmgen.create_conditional_block(name, self.llvmgen.current_block)
        else:
            (conditional_block, body_block, else_block, end_block) = \
                self.llvmgen.create_conditional_block_with_else(name,
                                                                self.llvmgen.current_block)

        # Create condition
        self.llvmgen.create_jump(conditional_block)
        self.llvmgen.enter_block(conditional_block)
        cond = self.transform_helper(nodes[0])
        self.llvmgen.create_conditional_jump(cond, body_block, end_block)

        # Create body
        self.llvmgen.enter_block(body_block)
        self.transform_helper(nodes[1])

        # Jump out of body
        self.llvmgen.create_jump_if_not_exists(end_block)

        # Create else if necessary
        if len(nodes) > 2:
            self.llvmgen.enter_block(else_block)
            self.transform_helper(nodes[2])
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
        cond = self.transform_helper(nodes[0])
        self.llvmgen.create_conditional_jump(cond, body_block, else_block)

        # Create body
        self.llvmgen.enter_block(body_block)
        true_value = self.transform_helper(nodes[1])

        # Jump out of body
        self.llvmgen.create_jump_if_not_exists(end_block)

        # Create else
        self.llvmgen.enter_block(else_block)
        false_value = self.transform_helper(nodes[2])
        self.llvmgen.create_jump_if_not_exists(end_block)

        # Leave conditional block
        self.llvmgen.enter_block(end_block)

        # PHI the values
        phi = self.llvmgen.builder.phi(true_value.type)
        phi.add_incoming(true_value, body_block.block)
        phi.add_incoming(false_value, else_block.block)

        return phi

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

    def function_call(self, tree: Tree):
        nodes = tree.children
        full_function_name: str
        function_name: str
        start = 1
        implicit_parameter = None
        instantiation = False

        if len(nodes) > 1 and not isinstance(nodes[1], Tree) and nodes[1].type == "IDENTIFIER":
            identifier = nodes[0].value
            full_function_name = function_name = nodes[1].value

            # Go along the nested properties to get to the function call
            for i, node in enumerate(nodes):
                # Skip first occurence since that is most likely the just-loaded variable
                if i == 0:
                    continue
                if not isinstance(node, Tree) and node.type == "IDENTIFIER":
                    # If next node is still identifier, we keep going
                    if len(nodes) > i + 1 and not isinstance(nodes[i + 1], Tree) and nodes[i + 1].type == "IDENTIFIER":
                        identifier += f".{node.value}"
                    else:
                        start = i + 1
                        break
                else:
                    start = i
                    break

            implicit_parameter = self.llvmgen.get_var(identifier)

        else:
            full_function_name = function_name = nodes[0].value

        i = start
        arguments: list = list()

        if implicit_parameter is not None:
            arguments.append(implicit_parameter)

        while i < len(nodes):
            if nodes[i] is None:
                continue
            arguments.append(self.transform_helper(nodes[i]))
            i += 1

        mangled_name = mangle_function_name(full_function_name, [arg.type for arg in arguments])

        # Check if it's an instantiation
        struct = ParserState.find_struct(full_function_name)

        if struct is not None:
            arguments.append(self.llvmgen.builder.alloca(struct))
            instantiation = True

        try:
            call_instr = self.llvmgen.gen_function_call(function_name, full_function_name, mangled_name, arguments)

            if instantiation:
                return arguments[0]
            return call_instr
        except IndexError:
            log_fail("Missing argument in function call")

        return None

    def function_decl(self, tree: Tree):
        nodes = tree.children

        node: MetadataToken = nodes[0]
        body_start = node.metadata['body_start']
        function_name = node.metadata['full_name']
        rial_arg_types = node.metadata['rial_arg_types']
        func = next((func for func in ParserState.module().functions if func.name == function_name), None)

        if func is None:
            raise KeyError("Expected a function but didn't find it!")

        self.llvmgen.create_function_body(func, rial_arg_types)

        i = body_start
        while i < len(nodes):
            self.transform_helper(nodes[i])
            i += 1

        self.llvmgen.finish_current_block()
        self.llvmgen.finish_current_func()

        return None
