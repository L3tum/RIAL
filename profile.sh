py-spy record -F -f raw -o profile.txt -- python3.8 -m rial.main "$@"
grep -v _find_and_load profile.txt > new_profile.txt
rm profile.txt
mv new_profile.txt profile.txt
~/FlameGraph/flamegraph.pl --colors js --width 7680 --inverted profile.txt > profile.svg

rm profile.txt
#rm new_profile.txt