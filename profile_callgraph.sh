python3.8 -m cProfile -s time -o profile.cg -m rial.main "$@"
gprof2dot -n 1 --skew=0.5 -f pstats profile.cg | dot -Tsvg -o callgraph.svg