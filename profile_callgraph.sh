python3.8 -m cProfile -s time -o profile.cg -m rial.main --workdir ./testing --disable-cache --compilation-units 1
gprof2dot -f pstats profile.cg | dot -Tsvg -o callgraph.svg