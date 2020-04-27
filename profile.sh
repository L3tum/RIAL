py-spy record -F -f raw -o profile.txt -- python3.8 -m rial.main --workdir testing --disable-cache --compilation-units 1
#grep -v _find_and_load profile.txt > new_profile.txt
~/FlameGraph/flamegraph.pl profile.txt > profile.svg

rm profile.txt
#rm new_profile.txt