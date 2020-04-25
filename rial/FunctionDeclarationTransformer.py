from typing import List, Tuple

from llvmlite import ir
from llvmlite.ir import IdentifiedStructType

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import is_builtin_type, map_shortcut_to_type
from rial.compilation_manager import CompilationManager
from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.concept.parser import Token, Discard, Tree
from rial.log import log_fail
from rial.metadata.FunctionDefinition import FunctionDefinition
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class FunctionDeclarationTransformer(TransformerInterpreter):
    mangling: bool
    llvmgen: LLVMGen

    def __init__(self):
        super().__init__()
        self.llvmgen = LLVMGen()
        self.mangling = True

    def attributed_func_decl(self, tree: Tree):
        nodes = tree.children
        attributes: List[Tree] = list()
        func_decl: Tree = None

        for node in nodes:
            if not isinstance(node, Tree):
                continue
            if node.data == "function_decl":
                func_decl = node
                break
            attributes.append(node)

        # TODO: Support actually implemented attributes
        for attribute in attributes:
            if attribute.children[0].value == "NoMangle":
                self.mangling = False

        func_decl = self.function_decl(func_decl)
        self.mangling = True
        return func_decl

    def function_decl(self, tree: Tree):
        nodes = tree.children
        access_modifier: RIALAccessModifier = RIALAccessModifier.PRIVATE
        linkage = "internal"
        external = False
        main_function = False
        calling_convention = "ccc"

        if nodes[0].type == "EXTERNAL":
            external = True
            linkage = "external"
            if nodes[1].type == "ACCESS_MODIFIER":
                return_type = nodes[2].value
                name = nodes[3].value
                start_args = 4
                access_modifier = RIALAccessModifier[nodes[1].value.upper()]
            else:
                return_type = nodes[1].value
                name = nodes[2].value
                start_args = 3
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

        args: List[Tuple[str, str]] = list()

        i = start_args
        var_args = False
        this_arg = None
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
            elif nodes[i].type == "THIS":
                i += 1
                this_arg = nodes[i].value
                this_arg = map_shortcut_to_type(this_arg)
                arg_type = nodes[i].value
                i += 1
                arg_name = nodes[i].value
                args.append((arg_type, arg_name))
                i += 1
                continue

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
        llvm_args = [ParserState.map_type_to_llvm(arg[0]) for arg in args if not arg[1].endswith("...")]

        # Convert struct arguments into reference arguments
        for llvm_arg in llvm_args:
            if isinstance(llvm_arg, IdentifiedStructType):
                index = llvm_args.index(llvm_arg)
                llvm_args.remove(llvm_arg)
                llvm_args.insert(index, ir.PointerType(llvm_arg))

        # Add class as implicit self parameter
        if self.llvmgen.current_struct is not None:
            llvm_args.insert(0, ir.PointerType(self.llvmgen.current_struct))
            args.insert(0, (self.llvmgen.current_struct.name, "this"))

        # If it's external we need to use the actual defined name instead of the compiler-internal one
        if external or self.mangling == False:
            full_function_name = name
        else:
            if self.llvmgen.current_struct is not None:
                full_function_name = mangle_function_name(name, llvm_args,
                                                          self.llvmgen.current_struct.name)
            else:
                if this_arg is not None:
                    full_function_name = mangle_function_name(name, llvm_args, this_arg)
                else:
                    full_function_name = mangle_function_name(name, llvm_args)
            full_function_name = f"{ParserState.module().name}:{full_function_name}"

        # Check if main method
        if full_function_name.endswith("main:main") and full_function_name.count(':') == 2:
            main_function = True

            # Check that main method returns either Int32 or void
            if return_type != "Int32" and return_type != "void":
                log_fail(f"Main method must return an integer status code or void, {return_type} given!")

        # Search for function in the archives
        # func = ParserState.search_function(full_function_name)

        # Function has been previously declared in other module
        # if func is not None and (func.module.name != ParserState.module().name or not func.is_declaration):
        #     # Check if either:
        #     # - has no body (cannot redeclare functions) or
        #     # - is already implemented and
        #     #   - is either public or
        #     #     - internal and
        #     #     - is in same package (cannot reimplement functions)
        #     # TODO: LLVM checks this anyways but maybe we wanna do it, too?
        #     log_fail(f"Function {full_function_name} already declared elsewhere")
        #     raise Discard()

        # Hasn't been declared previously, redeclare the function type here
        llvm_return_type = ParserState.map_type_to_llvm(return_type)
        func_type = self.llvmgen.create_function_type(llvm_return_type, llvm_args, var_args)

        # Create the actual function in IR
        func = self.llvmgen.create_function_with_type(full_function_name, func_type, linkage,
                                                      calling_convention,
                                                      list(map(lambda arg: arg[1], args)),
                                                      FunctionDefinition(return_type, access_modifier, args,
                                                                         self.llvmgen.current_struct is not None and self.llvmgen.current_struct.name or ""))

        if self.llvmgen.current_struct is not None:
            struct_def = self.llvmgen.current_struct.get_struct_definition()
            struct_def.functions.append(func.name)
            self.llvmgen.current_struct.module.update_named_metadata(
                f"{self.llvmgen.current_struct.name.replace(':', '_')}.definition", struct_def.to_list())

        # Always inline the main function into the compiler supplied one
        if main_function:
            func.attributes.add('alwaysinline')

        # If it has no body we do not need to go through it later as it's already declared with this method.
        if not has_body:
            raise Discard()

        if this_arg is not None:
            if is_builtin_type(this_arg):
                if this_arg not in CompilationManager.builtin_types:
                    CompilationManager.builtin_types[this_arg] = dict()

                CompilationManager.builtin_types[this_arg][func.name] = func

        token = nodes[0]
        metadata_token = MetadataToken(token.type, token.value)
        metadata_token.metadata["full_name"] = full_function_name
        metadata_token.metadata["body_start"] = i
        metadata_token.metadata['rial_arg_types'] = [arg[0] for arg in args]
        nodes.remove(token)
        nodes.insert(0, metadata_token)

        return Tree('function_decl', nodes)
