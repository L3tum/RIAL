python3.8 -m cProfile -s time -o main.profile -m rial.main --workdir ./testing --opt-level 3 --release

gprof2dot -f pstats main.profile | dot -Tsvg -o callgraph.svg