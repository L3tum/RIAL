from typing import List

from llvmlite import ir

from rial.compilation_manager import CompilationManager
from rial.concept.Transformer import Transformer
from rial.concept.combined_transformer import CombinedTransformer
from rial.concept.parser import Discard
from rial.ir.RIALFunction import RIALFunction
from rial.ir.RIALModule import RIALModule
from rial.ir.RIALVariable import RIALVariable
from rial.ir.modifier.AccessModifier import AccessModifier
from rial.transformer.builtin_type_to_llvm_mapper import null


class GlobalDeclarationTransformer(Transformer):
    main_transformer: CombinedTransformer
    module: RIALModule

    def __init__(self):
        super().__init__()
        self.module = CompilationManager.current_module

    def global_variable_decl(self, nodes: List):
        body = nodes[1].children
        access_modifier: AccessModifier = nodes[0].access_modifier
        variable_name = body[0].value
        value = body[2]

        if isinstance(value, RIALVariable):
            if value.is_global and value.value.global_constant:
                glob = self.module.declare_global(variable_name, value.rial_type, value.llvm_type,
                                                  access_modifier.get_linkage(), value.value.initializer,
                                                  access_modifier, True)
            else:
                with self.module.create_in_global_ctor():
                    glob = self.module.declare_global(variable_name, value.rial_type, value.llvm_type,
                                                      access_modifier.get_linkage(),
                                                      None, access_modifier)
                    self.module.builder.store(value.get_loaded_if_variable(self.module), glob.value)
        else:
            with self.module.create_in_global_ctor():
                if not isinstance(value, RIALFunction) and not isinstance(value, RIALVariable):
                    value: RIALVariable = self.main_transformer.visit(value)

                if isinstance(value, RIALFunction):
                    value: RIALFunction
                    # Check if in module, otherwise redeclare
                    # if self.module.get_global_safe(value.name) is None:
                    #     value = self.module.declare_function(value.name, value.canonical_name, value.function_type,
                    #                                          value.linkage, value.calling_convention, value.definition)

                    rial_type = str(value.function_type).replace("i8*", "Char[]")
                    glob = self.module.declare_global(variable_name, rial_type, value.function_type,
                                                      access_modifier.get_linkage(), value,
                                                      access_modifier, False)
                else:
                    glob = self.module.declare_global(variable_name, value.rial_type, value.llvm_type,
                                                      access_modifier.get_linkage(), null(value.llvm_type),
                                                      access_modifier)
                    self.module.builder.store(value.get_loaded_if_variable(self.module), glob.value)

        raise Discard()
