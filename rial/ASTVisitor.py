import base64
from typing import Tuple, List, Dict, Optional

from llvmlite import ir
from llvmlite.ir import Module, PointerType, FunctionType, GlobalVariable

from rial.LLVMFunction import LLVMFunction
from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import map_type_to_llvm, TRUE, FALSE
from rial.compilation_manager import CompilationManager
from rial.log import log_fail
from rial.builtin_type_to_llvm_mapper import NULL
from rial.concept.parser import Interpreter, Tree, Token


class ASTVisitor(Interpreter):
    ps: ParserState
    global_variables: Dict
    usings: List[str]
    llvmgen: LLVMGen

    def __init__(self, ps: ParserState, module: Module, filename: str, directory: str):
        di_file = module.add_debug_info("DIFile", {
            "filename": filename,
            "directory": directory,
        })
        di_compile_unit = module.add_debug_info("DICompileUnit", {
            "language": ir.DIToken("DW_LANG_C"),
            "file": di_file,
            "producer": "RIALC 0.1.0",
            "runtimeVersion": 1,
            "isOptimized": False,
        }, is_distinct=True)
        self.ps = ps
        self.global_variables = dict()
        self.usings = list()
        self.llvmgen = LLVMGen(module)

    def string(self, tree: Tree) -> GlobalVariable:
        nodes = tree.children
        value = nodes[0].value.strip("\"")
        name = ".const.string.%s" % base64.standard_b64encode(value.encode())
        glob = None

        if any(global_variable == name for global_variable in self.global_variables.keys()):
            glob = self.global_variables.get(name)
        else:
            glob = self.llvmgen.gen_string_lit(name, value)
            self.global_variables[name] = glob

        # Get pointer to first element
        # TODO: Change to return array and check in method signature for c-type stringiness
        return glob.gep([ir.Constant(ir.IntType(32), 0), ir.Constant(ir.IntType(32), 0)])

    def number(self, tree: Tree):
        nodes = tree.children
        return self.llvmgen.gen_integer(int(nodes[0].value), 32)

    def addition(self, tree: Tree):
        nodes = tree.children
        left = self.visit(nodes[0])
        right = self.visit(nodes[2])

        return self.llvmgen.gen_addition(left, right)

    def subtraction(self, tree: Tree):
        nodes = tree.children
        left = self.visit(nodes[0])
        right = self.visit(nodes[2])

        return self.llvmgen.gen_subtraction(left, right)

    def multiplication(self, tree: Tree):
        nodes = tree.children
        left = self.visit(nodes[0])
        right = self.visit(nodes[2])

        return self.llvmgen.gen_multiplication(left, right)

    def division(self, tree: Tree):
        nodes = tree.children
        left = self.visit(nodes[0])
        right = self.visit(nodes[2])

        return self.llvmgen.gen_division(left, right)

    def smaller_than(self, tree: Tree):
        nodes = tree.children
        left = self.visit(nodes[0])
        right = self.visit(nodes[2])

        return self.llvmgen.gen_comparison('<', left, right)

    def bigger_than(self, tree: Tree):
        nodes = tree.children
        left = self.visit(nodes[0])
        right = self.visit(nodes[2])

        return self.llvmgen.gen_comparison('>', left, right)

    def null(self, tree: Tree):
        return NULL

    def true(self, tree: Tree):
        return TRUE

    def false(self, tree: Tree):
        return FALSE

    def get_var(self, identifier: str):
        variable = self.llvmgen.current_block.get_named_value(identifier)

        if variable is None:
            log_fail(f"Variable not found {identifier}")
            return None

        return variable

    def var(self, tree: Tree):
        nodes = tree.children

        va = self.get_var(nodes[0].value)

        if isinstance(va.type, PointerType):
            return self.llvmgen.builder.load(va)

        return va

    def variable_increment(self, tree: Tree):
        nodes = tree.children
        variable = self.get_var(nodes[0].value)

        if len(nodes) > 1:
            value = self.visit(nodes[1])
        else:
            variable_type = variable.type

            if isinstance(variable_type, PointerType):
                variable_type = variable_type.pointee

            value = ir.Constant(variable_type, 1)

        return self.llvmgen.gen_shorthand(variable, value, '+')

    def variable_decrement(self, tree: Tree):
        nodes = tree.children
        variable = self.get_var(nodes[0].value)

        if len(nodes) > 1:
            value = self.visit(nodes[1])
        else:
            variable_type = variable.type

            if isinstance(variable_type, PointerType):
                variable_type = variable_type.pointee

            value = ir.Constant(variable_type, 1)

        return self.llvmgen.gen_shorthand(variable, value, '-')

    def variable_multiplication(self, tree: Tree):
        nodes = tree.children
        variable = self.get_var(nodes[0].value)
        value = self.visit(nodes[1])

        return self.llvmgen.gen_shorthand(variable, value, '*')

    def variable_division(self, tree: Tree):
        nodes = tree.children
        variable = self.get_var(nodes[0].value)
        value = self.visit(nodes[1])

        return self.llvmgen.gen_shorthand(variable, value, '/')

    def variable_assignment(self, tree: Tree):
        nodes = tree.children
        identifier = nodes[0].value
        value = self.visit(nodes[1])

        # TODO: Check if types are matching based on both LLVM value and inferred and metadata RIAL type
        return self.llvmgen.assign_to_variable(identifier, value)

    def variable_decl(self, tree: Tree):
        nodes = tree.children
        identifier = nodes[0].value
        value = self.visit(nodes[1])

        # TODO: Infer type based on value, essentially map LLVM type to RIAL type
        return self.llvmgen.declare_variable(identifier, value, str(value.type))

    def using(self, tree: Tree):
        mod_name = ':'.join(tree.children)
        CompilationManager.request_module(mod_name)
        self.usings.append(mod_name)

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

        return self.llvmgen.create_return_statement(self.visit(nodes[0]))

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
        self.visit(nodes[0])

        # Enter conditional block
        self.llvmgen.create_jump(conditional_block)
        self.llvmgen.enter_block(conditional_block)

        # Build condition
        condition = self.visit(nodes[1])
        self.llvmgen.create_conditional_jump(condition, body_block, end_block)

        # Go into body
        self.llvmgen.enter_block(body_block)

        # Build body
        i = 3
        while i < len(nodes):
            self.visit(nodes[i])
            i += 1

        # Build incrementor
        self.visit(nodes[2])

        # Jump back into condition
        self.llvmgen.create_jump(conditional_block)

        # Go out of loop
        self.llvmgen.enter_block(end_block)

    def while_loop(self, tree: Tree):
        nodes = tree.children
        name = self.llvmgen.current_block.block.name

        (conditional_block, body_block, end_block) = self.llvmgen.create_loop(name, self.llvmgen.current_block)

        # Enter conditional block
        self.llvmgen.create_jump(conditional_block)
        self.llvmgen.enter_block(conditional_block)

        # Build condition
        condition = self.visit(nodes[0])
        self.llvmgen.create_conditional_jump(condition, body_block, end_block)

        # Go into body
        self.llvmgen.enter_block(body_block)

        # Build body
        i = 1
        while i < len(nodes):
            self.visit(nodes[i])
            i += 1

        # Jump back into condition
        self.llvmgen.create_jump(conditional_block)

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
                self.llvmgen.create_conditional_block_with_else(name, self.llvmgen.current_block)

        # Create condition
        self.llvmgen.create_jump(conditional_block)
        self.llvmgen.enter_block(conditional_block)
        cond = self.visit(nodes[0])
        self.llvmgen.create_conditional_jump(cond, body_block, end_block)

        # Create body
        self.llvmgen.enter_block(body_block)
        self.visit(nodes[1])

        # Jump out of body
        if body_block.block.terminator is None:
            self.llvmgen.create_jump(end_block)

        # Create else if necessary
        if len(nodes) > 2:
            self.llvmgen.enter_block(else_block)
            self.visit(nodes[2])

            if else_block.block.terminator is None:
                self.llvmgen.create_jump(end_block)

        # Leave conditional block
        self.llvmgen.enter_block(end_block)

    def function_call(self, tree: Tree):
        nodes = tree.children
        function_name: str = nodes[0].value
        func = None

        # Check if function is called with namespace specification
        if ":" in function_name:
            true_function_name = function_name.split(':')[-1]
            mod_name = function_name.replace(":" + true_function_name, "")

            # Check if namespace is actually own namespace
            # Replace the full definition with the true function name (without namespace)
            if self.llvmgen.module.name == mod_name:
                function_name = true_function_name
            else:
                # Try to get the function by the full name
                llvm_function = self.ps.get_named_function(function_name)

                if llvm_function is None:
                    log_fail(f"Module {mod_name} does not define a function {true_function_name}")
                    return None

                function_name = true_function_name
                func = ir.Function(self.llvmgen.module, llvm_function.function_type, name=function_name)

        # If function doesn't contain namespace definition or namespace is own
        # Try to find function in current module
        if func is None:
            func = next((func for func in self.llvmgen.module.functions if func.name == function_name), None)

        # If function hasn't been found, iterate through the found usings and try to determine the function
        if func is None:
            functions_found: List[Tuple[str, LLVMFunction]] = list()

            for use in self.usings:
                llvm_function = self.ps.get_named_function(f"{use}:{function_name}")

                if llvm_function is None:
                    continue

                functions_found.append((use, llvm_function,))

            if len(functions_found) == 0:
                log_fail(f"Undeclared function {function_name} called!")
                return None

            if len(functions_found) > 1:
                log_fail(f"Function {function_name} has been declared multiple times!")
                log_fail(f"Specify the specific function to use by adding the namespace to the function call")
                log_fail(f"E.g. {functions_found[0][0]}:{function_name}()")
                return None

            func = ir.Function(self.llvmgen.module, functions_found[0][1].function_type, name=function_name)

        i = 1
        arguments: list = list()

        while i < len(nodes):
            if nodes[i] is None:
                continue

            arguments.append(self.visit(nodes[i]))
            i += 1

        try:
            self.llvmgen.builder.call(func, arguments)
        except IndexError:
            log_fail("Missing argument in function call")

    def function_decl(self, tree: Tree):
        nodes = tree.children
        access_modifier = "private"
        linkage = "internal"
        external = False

        if nodes[0].type == "EXTERNAL":
            return_type = nodes[1]
            name = nodes[2]
            start_args = 3
            external = True
            linkage = "external"
        elif nodes[0].type == "ACCESS_MODIFIER":
            access_modifier = nodes[0].value.lower()
            return_type = nodes[1]
            name = nodes[2]
            start_args = 3
            linkage = access_modifier == "public" and "external" or "internal"
        else:
            return_type = nodes[0]
            name = nodes[1]
            start_args = 2

        full_function_name = f"{self.llvmgen.module.name}:{name}"

        with self.ps.lock_and_search_named_function(full_function_name) as llvm_func:
            llvm_func: LLVMFunction
            llvm_function: Optional[LLVMFunction] = None
            args: List[Tuple[str, str]] = list()

            i = start_args
            var_args = False
            has_body = False

            while i < len(nodes):
                if not isinstance(nodes[i], Token):
                    has_body = True
                    break
                if var_args is True:
                    log_fail("PARAMS must be last in arguments")
                    break
                if nodes[i].type == "PARAMS":
                    var_args = True
                    i += 1
                if nodes[i].type == "IDENTIFIER":
                    arg_type = nodes[i]
                    i += 1
                    arg_name = nodes[i]

                    if var_args:
                        arg_name += "..."

                    args.append((arg_type, arg_name))
                    i += 1
                else:
                    break

            if has_body and external:
                log_fail("External functions cannot have a body!")
                return None

            if has_body and var_args:
                log_fail(f"Non-externally defined functions currently cannot have a PARAMS variable length parameter")
                return None

            if llvm_func is not None:
                if has_body == False or name in self.ps.implemented_functions:
                    log_fail(f"Function {name} already declared elsewhere")
                    return None

                llvm_function = llvm_func

            if llvm_function is None:
                llvm_args = [map_type_to_llvm(arg[0]) for arg in args if not arg[1].endswith("...")]
                llvm_return_type = map_type_to_llvm(return_type)
                func_type = self.llvmgen.create_function_type(llvm_return_type, llvm_args, var_args)
            else:
                func_type = llvm_function.function_type

            # Only add the function type to "globally" available functions if it's externally available
            if linkage == "external":
                llvm_function = LLVMFunction(func_type, access_modifier, self.llvmgen.module.name)
                self.ps.functions[full_function_name] = llvm_function

        func = self.llvmgen.create_function_with_type(name, func_type, linkage, list(map(lambda arg: arg[1], args)),
                                                      has_body, access_modifier, str(llvm_return_type),
                                                      list(map(lambda arg: arg[0], args)))

        if has_body:
            while i < len(nodes):
                self.visit(nodes[i])
                i += 1

            self.llvmgen.finish_current_block()

        return None
