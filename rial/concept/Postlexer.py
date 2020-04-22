from rial.builtin_type_to_llvm_mapper import map_shortcut_to_type
from rial.compilation_manager import CompilationManager


class Postlexer:
    def identifier(self, token):
        value = token.value
        value = map_shortcut_to_type(value)

        # TODO: Add some kind of external registration / handling of this instead of inlining it all into this function
        if value.startswith("#"):
            if value == "#programMain":
                value = f"{CompilationManager.config.project_name}:main:main"
            elif value == "#targetTriple":
                value = CompilationManager.codegen.target_machine.triple
                token.type = "STRING"
            elif value == "#targetOS":
                triple = CompilationManager.codegen.target_machine.triple
                token.type = "STRING"

                # TODO: Better detection
                if '-linux-' in triple:
                    value = "linux"
                elif "-windows-" in triple:
                    value = "windows"
                elif "-darwin-" in triple:
                    value = "darwin"
                else:
                    value = triple

        token.value = value

        return token

    def process(self, stream):
        # Process token stream
        for token in stream:
            if token.type == "IDENTIFIER":
                yield self.identifier(token)
            else:
                yield token

    # No idea why this is needed
    @property
    def always_accept(self):
        return ()
