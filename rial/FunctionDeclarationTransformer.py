from typing import List, Tuple

from llvmlite import ir
from rial.LLVMFunction import LLVMFunction
from rial.SingleParserState import SingleParserState
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.concept.parser import Transformer_InPlaceRecursive, Token, Discard, Tree
from rial.log import log_fail
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class FunctionDeclarationTransformer(Transformer_InPlaceRecursive):
    sps: SingleParserState

    def init(self, sps: SingleParserState):
        self.sps = sps

    def function_decl(self, nodes):
        access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE
        linkage = "internal"
        external = False
        main_function = False
        calling_convention = "ccc"

        if nodes[0].type == "EXTERNAL":
            return_type = nodes[1].value
            name = nodes[2].value
            start_args = 3
            external = True
            linkage = "external"
            access_modifier = RIALAccessModifier.PUBLIC
        elif nodes[0].type == "ACCESS_MODIFIER":
            access_modifier = RIALAccessModifier[nodes[0].value.upper()]
            return_type = nodes[1].value
            name = nodes[2].value
            start_args = 3
            linkage = access_modifier.get_linkage()
        else:
            return_type = nodes[0].value
            name = nodes[1].value
            start_args = 2

        full_function_name = f"{self.sps.llvmgen.module.name}:{name}"
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
                arg_type = nodes[i].value
                i += 1
                arg_name = nodes[i].value

                if var_args:
                    arg_name += "..."

                args.append((arg_type, arg_name))
                i += 1
            else:
                break

        if has_body and external:
            log_fail("External functions cannot have a body!")
            raise Discard()

        if has_body and var_args:
            log_fail(f"Non-externally defined functions currently cannot have a PARAMS variable length parameter")
            raise Discard()

        # Map RIAL args to llvm arg types
        llvm_args = [self.sps.map_type_to_llvm(arg[0]) for arg in args if not arg[1].endswith("...")]

        # Add class as implicit self parameter
        if self.sps.llvmgen.current_struct is not None:
            llvm_args.insert(0, ir.PointerType(self.sps.llvmgen.current_struct.struct))
            args.insert(0, (self.sps.llvmgen.current_struct.name, "this"))

        # Check if main method
        if full_function_name.endswith("main:main") and full_function_name.count(':') == 2:
            main_function = True

            # Check that main method returns either Int32 or void
            if return_type != "Int32" and return_type != "void":
                log_fail(f"Main method must return an integer status code or void, {return_type} given!")

        # If it's external we need to use the actual defined name instead of the compiler-internal one
        if external:
            full_function_name = name
        else:
            full_function_name = mangle_function_name(full_function_name, [str(arg) for arg in llvm_args])

        # Search for function in the archives
        llvm_func = self.sps.ps.search_function(full_function_name)

        # Function has been previously declared
        if llvm_func is not None:
            # Check if either:
            # - has no body (cannot redeclare functions) or
            # - is already implemented and
            #   - is either public or
            #     - internal and
            #     - is in same package (cannot reimplement functions)
            if has_body == False or full_function_name in self.sps.ps.implemented_functions and (
                    llvm_func.access_modifier == "public" or (
                    llvm_func.access_modifier == "internal" and llvm_func.module.split(':')[0] ==
                    self.sps.llvmgen.module.name.split(':')[0])):
                log_fail(f"Function {full_function_name} already declared elsewhere")
                raise Discard()
        else:
            # Hasn't been declared previously, redeclare the function type here
            llvm_return_type = self.sps.map_type_to_llvm(return_type)
            func_type = self.sps.llvmgen.create_function_type(llvm_return_type, llvm_args, var_args)
            llvm_func = LLVMFunction(full_function_name, func_type, access_modifier, self.sps.llvmgen.module.name,
                                     return_type)
            self.sps.ps.functions[full_function_name] = llvm_func
            self.sps.ps.main_function = llvm_func

        # Create the actual function in IR
        func = self.sps.llvmgen.create_function_with_type(full_function_name, llvm_func.function_type, linkage,
                                                          calling_convention,
                                                          list(map(lambda arg: arg[1], args)),
                                                          has_body, access_modifier,
                                                          llvm_func.rial_return_type)

        # Always inline the main function into the compiler supplied one
        if main_function:
            func.attributes.add('alwaysinline')

        # If it's in a struct or class we add it to that struct archives
        if self.sps.llvmgen.current_struct is not None:
            self.sps.llvmgen.current_struct.functions.append(func)

        # If it has no body we do not need to go through it later as it's already declared with this method.
        if not has_body:
            raise Discard()

        token = nodes[0]
        metadata_token = MetadataToken(token.type, token.value)
        metadata_token.metadata["full_name"] = full_function_name
        metadata_token.metadata["body_start"] = i
        metadata_token.metadata['rial_arg_types'] = [arg[0] for arg in args]
        nodes: List
        nodes.remove(token)
        nodes.insert(0, metadata_token)

        return Tree('function_decl', nodes)
