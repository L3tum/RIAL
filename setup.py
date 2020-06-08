import os
import subprocess
import sys
from pathlib import Path
from shutil import which

from setuptools import setup
from setuptools.command.install import install


def run_command(command: str, cwd: str):
    process = subprocess.Popen(command, shell=True, cwd=cwd)
    process.wait()
    if process.returncode != 0:
        sys.exit(process.returncode)


class CompilerRTInstall(install):
    def run(self):
        llvm_project_path = Path(os.getcwd()).joinpath("llvm_project")
        compiler_rt_src_path = llvm_project_path.joinpath("compiler-rt")
        compiler_rt_build_path = llvm_project_path.joinpath("compiler-rt-build")

        llvm_project_path.mkdir(parents=False, exist_ok=False)

        # Init git repo and enable sparse checkout
        command = "git init && git remote add origin https://github.com/llvm/llvm-project.git && git config core.sparseCheckout true"
        run_command(command, str(llvm_project_path))

        # Only pull compiler-rt directories
        print("Selecting compiler-rt")
        with open(llvm_project_path.joinpath(".git").joinpath("info").joinpath("sparse-checkout"), "w") as file:
            file.write("compiler-rt/")

        # Pull 8.x branch
        command = "git pull --depth=1 origin release/8.x"
        run_command(command, str(llvm_project_path))

        # Build compiler-rt
        compiler_rt_build_path.mkdir(parents=False, exist_ok=False)

        llvm_config = which("llvm-config")

        if llvm_config is None:
            llvm_config = which("llvm-config-8")

        if llvm_config is None:
            raise FileNotFoundError("Missing llvm-config or llvm-config-8 in PATH")
        command = f"cmake {str(compiler_rt_src_path)} -DLLVM_CONFIG_PATH={llvm_config} && make"
        process = subprocess.Popen(command, shell=True, cwd=str(compiler_rt_build_path))
        process.wait()
        if process.returncode != 0:
            sys.exit(process.returncode)

        # Install yourself
        # install.run(self)


setup(
    name='RIAL',
    version='0.0.1',
    packages=['rial', 'rial.stages', 'rial.stages.post_parsing', 'rial.stages.post_ir_generation', 'rial.concept',
              'rial.linking', 'rial.metadata', 'rial.rial_types', 'rial.platform_support', 'tests'],
    url='https://github.com/L3tum/RIAL',
    license='MIT',
    author='L3tum',
    author_email='',
    description='',
    cmdclass={'install': CompilerRTInstall},
)
