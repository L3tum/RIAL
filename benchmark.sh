echo "Current task-clock:u is ~410 msec"
echo "Current seconds elapsed is ~1 second"

perf stat -r 10 -d python3.8 -m rial.main --workdir testing --disable-cache