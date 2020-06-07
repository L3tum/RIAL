from typing import List

from llvmlite.ir import Type, FunctionType, FunctionAttributes, ArrayType, re

from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.parser import Tree, Discard
from rial.ir.RIALFunction import RIALFunction
from rial.ir.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.ir.RIALModule import RIALModule
from rial.ir.RIALVariable import RIALVariable
from rial.ir.metadata.FunctionDefinition import FunctionDefinition
from rial.ir.metadata.metadata_token import MetadataToken
from rial.ir.modifier.AccessModifier import AccessModifier
from rial.transformer.builtin_type_to_llvm_mapper import map_shortcut_to_type, is_builtin_type
from rial.util.log import log_fail


class FunctionDeclarationTransformer(TransformerInterpreter):
    attributes: FunctionAttributes
    module: RIALModule
    default_cc = "fastcc"

    def __init__(self, module: RIALModule):
        self.module = module
        self.attributes = FunctionAttributes()

    def function_decl_args(self, tree: Tree):
        nodes = tree.children
        args: List[RIALVariable] = list()

        i = 0
        var_args = False
        while i < len(nodes):
            if var_args:
                raise KeyError()

            # Params
            if not isinstance(nodes[i], List):
                var_args = True
                i += 1

            ty = self.module.get_definition(nodes[i])
            i += 1
            name = nodes[i].value
            i += 1

            if var_args:
                name = f"{name}..."

            if isinstance(ty, RIALVariable):
                rial_type = ty.rial_type
                llvm_type = ty.llvm_type
            elif isinstance(ty, RIALIdentifiedStructType):
                rial_type = ty.name
                llvm_type = ty
            elif isinstance(ty, RIALModule):
                raise KeyError(ty)
            elif isinstance(ty, RIALFunction):
                rial_type = str(ty.function_type)
                llvm_type = ty.function_type
            elif isinstance(ty, Type):
                rial_type = map_shortcut_to_type('.'.join(nodes[i - 2]))
                llvm_type = ty
            else:
                rial_type = None
                llvm_type = None

            args.append(RIALVariable(name, rial_type, llvm_type, None))

        return args

    def builtin_attribute(self, tree: Tree):
        nodes = tree.children
        for node in nodes:
            if node == "no_mangle":
                self.attributes.add('noduplicate')
            elif node == "cold":
                self.attributes.add('cold')
            elif node == "inline(always)":
                self.attributes.add("alwaysinline")
            elif node == "inline(never)":
                self.attributes.add("neverinline")
            elif node == "inline":
                self.attributes.add("inlinehint")

    def attributed_func_decl(self, tree: Tree):
        nodes = tree.children
        attributes: List[Tree] = list()
        func_decl: Tree = None

        for node in nodes:
            if not isinstance(node, Tree):
                continue
            if node.data == "function_decl" or node.data == "extension_function_decl" or node.data == "external_function_decl":
                func_decl = node
                break
            attributes.append(node)

        for attribute in attributes:
            if attribute.data == "builtin_attribute":
                self.visit(attribute)
            else:
                # TODO: Support actually implemented attributes
                pass

        func_decl = self.visit(func_decl)
        self.attributes = FunctionAttributes()
        return func_decl

    def external_function_decl(self, tree: Tree):
        nodes = tree.children
        access_modifier: AccessModifier = nodes[0].access_modifier
        unsafe: bool = nodes[0].unsafe
        name = nodes[2].value
        llvm_return_type = self.module.get_definition(nodes[1])

        if isinstance(llvm_return_type, RIALIdentifiedStructType):
            return_type = llvm_return_type.name
        else:
            return_type = map_shortcut_to_type('.'.join(nodes[1]))

        # Builtins can be passed as raw values
        if is_builtin_type(return_type):
            llvm_return_type = llvm_return_type
        # Pointer to first element for still normal arrays
        elif re.match(r".+\[[0-9]+\]$", return_type) is not None:
            llvm_return_type = llvm_return_type.as_pointer()
        elif isinstance(llvm_return_type, RIALIdentifiedStructType):
            llvm_return_type = llvm_return_type.as_pointer()
        else:
            llvm_return_type = llvm_return_type

        # External functions cannot be declared in a struct
        if self.module.current_struct is not None:
            log_fail(f"External function {name} cannot be declared inside a class!")
            raise Discard()

        args: List[RIALVariable] = self.visit(nodes[3])

        if not unsafe and not self.llvmgen.currently_unsafe:
            raise PermissionError("Can only declare external functions in unsafe blocks or as unsafe functions.")

        llvm_args = list()

        # Map RIAL args to llvm arg types
        for arg in args:
            if arg.name.endswith("..."):
                continue

            # Pointer for array and struct types
            if isinstance(arg.llvm_type, RIALIdentifiedStructType) or isinstance(arg.llvm_type, ArrayType):
                llvm_type = arg.llvm_type.as_pointer()
            else:
                llvm_type = arg.llvm_type
            llvm_args.append(llvm_type)

        var_args = len(args) > 0 and args[-1].name.endswith("...")

        # Hasn't been declared previously, redeclare the function type here
        func_type = FunctionType(llvm_return_type, llvm_args, var_args)

        # Create function definition
        func = RIALFunction(self.module, func_type, name, name)
        func.linkage = "external"
        func.calling_convention = "ccc"
        func.definition = FunctionDefinition(return_type, access_modifier, args, unsafe=True)
        func.attributes = self.attributes

        # Update args
        for i, arg in enumerate(func.args):
            arg.name = args[i].name
            args[i].value = arg

        raise Discard()

    def extension_function_decl(self, tree: Tree):
        nodes = tree.children
        access_modifier: AccessModifier = nodes[0].access_modifier
        unsafe: bool = nodes[0].unsafe
        linkage = access_modifier.get_linkage()
        calling_convention = self.default_cc
        name = nodes[2].value
        llvm_return_type = self.module.get_definition(nodes[1])

        if isinstance(llvm_return_type, RIALIdentifiedStructType):
            return_type = llvm_return_type.name
        else:
            return_type = map_shortcut_to_type('.'.join(nodes[1]))

        # Builtins can be passed as raw values
        if is_builtin_type(return_type):
            llvm_return_type = llvm_return_type
        # Pointer to first element for still normal arrays
        elif re.match(r".+\[[0-9]+\]$", return_type) is not None:
            llvm_return_type = llvm_return_type.as_pointer()
        elif isinstance(llvm_return_type, RIALIdentifiedStructType):
            llvm_return_type = llvm_return_type.as_pointer()
        else:
            llvm_return_type = llvm_return_type

        # Extension functions cannot be declared inside other classes.
        if self.module.current_struct is not None:
            log_fail(f"Extension function {name} cannot be declared inside another class!")
            raise Discard()

        args: List[RIALVariable] = list()
        this_type = self.module.get_definition(nodes[3])

        if isinstance(this_type, RIALIdentifiedStructType):
            rial_type = this_type.name
        else:
            rial_type = map_shortcut_to_type('.'.join(nodes[3]))

        args.append(RIALVariable(nodes[4].value, rial_type, this_type, None))

        if isinstance(nodes[5], Tree) and nodes[5].data == "function_decl_args":
            args.extend(self.visit(nodes[5]))
            body_start = 6
        else:
            body_start = 5

        # If the function has the NoMangleAttribute we need to use the normal name
        if 'noduplicate' in self.attributes:
            full_function_name = name
        else:
            full_function_name = self.module.get_unique_function_name(name, [arg.rial_type for arg in args])

        llvm_args = list()

        # Map RIAL args to llvm arg types
        for arg in args:
            if arg.name.endswith("..."):
                continue

            # Builtins can be passed as raw values
            if is_builtin_type(arg.rial_type):
                llvm_args.append(arg.llvm_type)
            # Pointer to first element for still normal arrays
            elif re.match(r".+\[[0-9]+\]$", arg.rial_type) is not None:
                llvm_args.append(arg.llvm_type.as_pointer())
            elif isinstance(arg.llvm_type, RIALIdentifiedStructType):
                llvm_args.append(arg.llvm_type.as_pointer())
            else:
                llvm_args.append(arg.llvm_type)

        # Hasn't been declared previously, redeclare the function type here
        func_type = FunctionType(llvm_return_type, llvm_args)

        # Create the actual function in IR
        func = RIALFunction(self.module, func_type, full_function_name, name)
        func.linkage = linkage
        func.calling_convention = calling_convention
        func.definition = FunctionDefinition(return_type, access_modifier, args, args[0].rial_type, unsafe)

        # Update args
        for i, arg in enumerate(func.args):
            arg.name = args[i].name
            args[i].value = arg

        # If it has no body we can discard it now.
        if len(nodes) <= body_start:
            raise Discard()

        token = nodes[2]
        metadata_token = MetadataToken(token.type, token.value)
        metadata_token.metadata["func"] = func
        metadata_token.metadata["body_start"] = body_start
        nodes.remove(token)
        nodes.insert(0, metadata_token)

        return Tree('function_decl', nodes)

    def function_decl(self, tree: Tree):
        nodes = tree.children
        access_modifier: AccessModifier = nodes[0].access_modifier
        unsafe: bool = nodes[0].unsafe
        linkage = access_modifier.get_linkage()
        calling_convention = self.default_cc
        name = nodes[2].value
        llvm_return_type = self.module.get_definition(nodes[1])

        if isinstance(llvm_return_type, RIALIdentifiedStructType):
            return_type = llvm_return_type.name
        else:
            return_type = map_shortcut_to_type('.'.join(nodes[1]))

        # Builtins can be passed as raw values
        if is_builtin_type(return_type):
            llvm_return_type = llvm_return_type
        # Pointer to first element for still normal arrays
        elif re.match(r".+\[[0-9]+\]$", return_type) is not None:
            llvm_return_type = llvm_return_type.as_pointer()
        elif isinstance(llvm_return_type, RIALIdentifiedStructType):
            llvm_return_type = llvm_return_type.as_pointer()
        else:
            llvm_return_type = llvm_return_type

        args: List[RIALVariable] = list()

        # Add class as implicit parameter
        if self.module.current_struct is not None:
            args.append(RIALVariable("this", self.module.current_struct.name, self.module.current_struct, None))

        args.extend(self.visit(nodes[3]))

        llvm_args = list()

        # Map RIAL args to llvm arg types
        for arg in args:
            if arg.name.endswith("..."):
                continue

            # Pointer for array and struct types
            if isinstance(arg.llvm_type, RIALIdentifiedStructType) or isinstance(arg.llvm_type, ArrayType):
                llvm_type = arg.llvm_type.as_pointer()
            else:
                llvm_type = arg.llvm_type
            llvm_args.append(llvm_type)

        # If the function has the NoMangleAttribute we need to use the normal name
        if 'noduplicate' in self.attributes:
            full_function_name = name
        else:
            full_function_name = self.module.get_unique_function_name(name, [arg.rial_type for arg in args])

        # Check if main method
        if name.endswith("main") and self.module.name.endswith("main"):
            self.attributes.add('alwaysinline')

            # Check that main method returns either Int32 or void
            if return_type != "Int32" and return_type != "Void":
                log_fail(f"Main method must return an integer status code or void, {return_type} given!")

        # Hasn't been declared previously, redeclare the function type here
        func_type = FunctionType(llvm_return_type, llvm_args, False)

        # Create the actual function in IR
        func = RIALFunction(self.module, func_type, full_function_name, name)
        func.linkage = linkage
        func.calling_convention = calling_convention
        func.definition = FunctionDefinition(return_type, access_modifier, args,
                                             self.module.current_struct is not None and self.module.current_struct or "",
                                             unsafe)
        func.attributes = self.attributes

        # Update args
        for i, arg in enumerate(func.args):
            arg.name = args[i].name
            args[i].value = arg

        # If it has no body we do not need to go through it later as it's already declared with this method.
        if not len(nodes) > 4:
            raise Discard()

        token = nodes[2]
        metadata_token = MetadataToken(token.type, token.value)
        metadata_token.metadata["func"] = func
        metadata_token.metadata["body_start"] = 4
        nodes.remove(token)
        nodes.insert(0, metadata_token)

        return Tree('function_decl', nodes)
