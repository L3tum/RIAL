from rial.concept import parser
from rial.concept.parser import Discard


class Transformer(parser.Transformer):
    def transform(self, tree):
        try:
            return super().transform(tree)
        except Discard:
            pass
        except Exception as e:
            from rial.util.log import log_fail
            log_fail(e)
            from rial.compilation_manager import CompilationManager
            log_fail(
                f"Current Module: {CompilationManager.current_module is not None and CompilationManager.current_module.name or ''}")
            import traceback
            log_fail(traceback.format_exc())
