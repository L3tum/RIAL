from rial.compilation_manager import CompilationManager
from rial.concept.parser import Token


class Postlexer:
    def identifier(self, token: Token):
        value: str = token.value

        # TODO: Add some kind of external registration / handling of this instead of inlining it all into this function
        if value.startswith("#"):
            if value == "#programMainModule":
                value = f"{CompilationManager.config.project_name}:main"
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
        elif token.startswith("@"):
            value = value.replace("@", "").strip("\"")

        token = token.update(value=value)

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
