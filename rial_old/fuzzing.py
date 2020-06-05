import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from random import random

from pythonfuzz.main import PythonFuzz


class Result(object):
    """
    Use the output from the tool to collect the information about its execution.
    Very sensitive to the format of the output as to whether it collects information or not.
    """
    coverage_re = re.compile('cov: (\d+)')
    corpus_re = re.compile('corp: (\d+)')
    speed_re = re.compile('exec/s: (\d+)')
    memory_re = re.compile('rss: (\d+\.\d+)')
    count_re = re.compile('^#(\d+)')
    count2_re = re.compile('^did (\d+) runs, stopping now')
    exception_re = re.compile('^Exception: (.*)')
    failfile_re = re.compile('^sample written to (.*)')

    def __init__(self):
        self.coverage = None
        self.corpus = None
        self.speed = None
        self.memory = None
        self.count = None
        self.time_start = None
        self.time_end = None
        self.fail_file = None
        self.exception = None
        self.lines = []
        self.rc = None

    def record_start(self):
        self.time_start = time.time()

    def record_end(self):
        self.time_end = time.time()

    @property
    def time_duration(self):
        """
        Number of seconds the execution took, or None if not known
        """
        if self.time_start and self.time_end:
            return self.time_end - self.time_start
        if self.time_start:
            return time.time() - self.time_start

        return None

    def process_output(self, line):
        match = self.coverage_re.search(line)
        if match:
            self.coverage = int(match.group(1))

        match = self.corpus_re.search(line)
        if match:
            self.corpus = int(match.group(1))

        match = self.speed_re.search(line)
        if match:
            self.speed = int(match.group(1))

        match = self.memory_re.search(line)
        if match:
            self.memory = float(match.group(1))

        match = self.count_re.search(line) or self.count2_re.search(line)
        if match:
            self.count = int(match.group(1))

        match = self.exception_re.search(line)
        if match:
            self.exception = match.group(1)

        match = self.failfile_re.search(line)
        if match:
            self.fail_file = match.group(1)

        self.lines.append(line)

    def show(self, show_lines=False, indent=''):
        """
        Show the status of this result.
        """
        print("{}Executions       : {}".format(indent, self.count))
        print("{}Corpus           : {}".format(indent, self.corpus))
        print("{}Coverage         : {}".format(indent, self.coverage))
        print("{}Final speed      : {}/s".format(indent, self.speed))
        if self.memory:
            print("{}Memory           : {:.2f} MB".format(indent, self.memory))
        print("{}Runtime          : {:.2f} s".format(indent, self.time_duration))
        if self.time_duration and self.count:
            print("{}Overall speed    : {:.2f}/s".format(indent, self.count / self.time_duration))
        print("{}Return code      : {}".format(indent, self.rc))
        if self.exception:
            print("{}Exception        : {}".format(indent, self.exception))
        if self.fail_file:
            print("{}Failed filename  : {}".format(indent, self.fail_file))

        if show_lines or self.rc:
            print("{}Lines:".format(indent))
            for line in self.lines:
                print("{}  {}".format(indent, line.strip('\n')))


def run(cwd, workdir, python='python', log='/dev/null'):
    """
    Run the script, capturing the output and processing it.
    """
    cmd = [python, '-m', 'rial.main', '--workdir', workdir]

    result = Result()
    with open(log, 'w') as log_fh:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)
        result.record_start()
        for line in proc.stdout:
            line = line.decode('utf-8', 'replace')
            result.process_output(line)
        result.record_end()

        proc.wait()
        result.rc = proc.returncode

    return result


@PythonFuzz
def fuzz(buf):
    try:
        string = buf.decode("utf-8")
    except UnicodeDecodeError:
        return
    cur_directory = Path(__file__.replace("fuzzing.py", ""))
    tmp_directory = cur_directory.joinpath(f"tmp_{random()}")
    tmp_directory.mkdir(parents=False, exist_ok=False)
    src_directory = tmp_directory.joinpath("src")
    src_directory.mkdir(parents=False, exist_ok=False)

    with open(src_directory.joinpath("main.rial"), "w") as file:
        file.write(string)

    try:
        result = run(str(cur_directory.joinpath("..")), tmp_directory, sys.executable)
        result.show(indent='  ')
    except:
        raise
    finally:
        shutil.rmtree(tmp_directory)


if __name__ == '__main__':
    fuzz(dirs=[str(Path(__file__.replace("fuzzing.py", "").replace("/rial", "")).joinpath("fuzzing_out")),
               str(Path(__file__.replace("fuzzing.py", "").replace("/rial", "")).joinpath("fuzzing_in"))])
