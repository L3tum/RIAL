from typing import List, Tuple, Optional

from llvmlite import ir
from llvmlite.ir import Module, Function

from rial.LLVMFunction import LLVMFunction
from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import map_type_to_llvm
from rial.compilation_manager import CompilationManager
from rial.log import log_fail
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class SingleParserState:
    usings: List[str]
    llvmgen: LLVMGen

    def __init__(self, module: Module):
        self.usings = list()
        self.llvmgen = LLVMGen(module)

    def find_function(self, full_function_name: str) -> Optional[Function]:
        # Try to find function in current module
        func = next((func for func in self.llvmgen.module.functions if func.name == full_function_name), None)

        # Try to find function in current module with module specifier
        if func is None:
            func = next((func for func in self.llvmgen.module.functions if
                         func.name == f"{self.llvmgen.module.name}:{full_function_name}"), None)

        # If func isn't in current module
        if func is None:
            # Try to find function by full name
            llvm_function = ParserState.search_function(full_function_name)

            # If couldn't find it, iterate through usings and try to find function
            if llvm_function is None:
                functions_found: List[Tuple[str, LLVMFunction]] = list()

                for use in self.usings:
                    llvm_function = ParserState.search_function(f"{use}:{full_function_name}")
                    if llvm_function is None:
                        continue
                    functions_found.append((use, llvm_function,))

                if len(functions_found) > 1:
                    log_fail(f"Function {full_function_name} has been declared multiple times!")
                    log_fail(f"Specify the specific function to use by adding the namespace to the function call")
                    log_fail(f"E.g. {functions_found[0][0]}:{full_function_name}()")
                    return None

                # Check for number of functions found
                if len(functions_found) == 1:
                    llvm_function = functions_found[0][1]

            if llvm_function is not None:
                # Function is either:
                # - public or
                # - internal and
                #   - in same TLM
                if llvm_function.access_modifier != RIALAccessModifier.PUBLIC and \
                        (llvm_function.access_modifier != RIALAccessModifier.INTERNAL and
                         llvm_function.module.split(':')[0]
                         == self.llvmgen.module.name.split(':')[0]):
                    log_fail(
                        f"Cannot access method {full_function_name} in module {llvm_function.module}!")
                    return None

                func = ir.Function(self.llvmgen.module, llvm_function.function_type, name=llvm_function.name)

        # Try request the module that the function might(!) be in
        if func is None:
            if ":" in full_function_name:
                mod_name = ':'.join(full_function_name.split(':')[0:-1])

                # Check that the module hasn't been compiled yet
                if not CompilationManager.check_module_already_compiled(mod_name):
                    CompilationManager.request_module(mod_name)
                    return self.find_function(full_function_name)

        return func

    def find_struct(self, struct_name: str):
        struct = ParserState.search_structs(struct_name)

        if struct is None:
            struct = ParserState.search_structs(f"{self.llvmgen.module.name}:{struct_name}")

        if struct is None:
            structs_found: List[Tuple] = list()
            for using in self.usings:
                s = ParserState.search_structs(f"{using}:{struct_name}")

                if s is not None:
                    structs_found.append((using, s))
            if len(structs_found) == 0:
                return None

            if len(structs_found) > 1:
                log_fail(f"Multiple declarations found for {struct_name}")
                log_fail(f"Specify one of them by using {structs_found[0][0]}:{struct_name} for example")
                return None
            struct = structs_found[0][1]

        return struct

    def map_type_to_llvm(self, name: str):
        llvm_type = map_type_to_llvm(name)

        # Check if builtin type
        if llvm_type is None:
            llvm_struct = self.find_struct(name)

            if llvm_struct is not None:
                llvm_type = llvm_struct.struct
            else:
                log_fail(f"Referenced unknown type {name}")
                return None

        return llvm_type
