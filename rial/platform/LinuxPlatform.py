from shutil import which

from rial.linking.linking_options import LinkingOptions
from rial.platform.IPlatform import IPlatform


class LinuxPlatform(IPlatform):
    def get_source_file_extension(self) -> str:
        return super().get_source_file_extension()

    def get_object_file_extension(self) -> str:
        return super().get_object_file_extension()

    def get_asm_file_extension(self) -> str:
        return super().get_asm_file_extension()

    def get_ir_file_extension(self) -> str:
        return super().get_ir_file_extension()

    def get_bc_file_extension(self) -> str:
        return super().get_bc_file_extension()

    def get_exe_file_extension(self) -> str:
        return ""

    def get_link_options(self) -> LinkingOptions:
        opts = LinkingOptions()
        opts.linker_executable = which("clang-8")

        if opts.linker_executable is None:
            opts.linker_executable = which("clang")

        if opts.linker_executable is None:
            opts.linker_executable = which("cc")

        opts.llvm_linker_executable = which("llvm-link-8")

        if opts.llvm_linker_executable is None:
            opts.llvm_linker_executable = which("llvm-link")

        # Detect underlinking (missing shared libraries)
        opts.linker_pre_args.append("-Wl,-z,defs")

        # Enable Adress space layout randomization via position-independent-executables
        # TODO: Disable when building a shared library
        # opts.linker_pre_args.append("-fPIE -Wl,-pie")

        # Use the "new" stack protector
        opts.linker_pre_args.append("-fstack-protector-strong")

        # Integer overflow wraps around (and isn't undefined)
        opts.linker_pre_args.append("-fwrapv")

        # Enable link-time-optimizations (LTO)
        opts.linker_pre_args.append("-flto -ffat-lto-objects")

        # We want to be able to strip as much executable code as possible
        # from the linker command line, and this flag indicates to the
        # linker that it can avoid linking in dynamic libraries that don't
        # actually satisfy any symbols up to that point (as with many other
        # resolutions the linker does). This option only applies to all
        # following libraries so we're sure to pass it as one of the first
        # arguments. (Taken from Rust)
        opts.linker_pre_args.append("-Wl,--as-needed")

        # Always enable NX protection when it is available
        opts.linker_pre_args.append("-Wl,-z,noexecstack")

        # Use 64-bit
        opts.linker_pre_args.append("-m64")

        return opts
