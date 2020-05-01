import yappi

from rial.main import start

yappi.set_clock_type("cpu")
yappi.start()
start()
yappi.stop()

# retrieve thread stats by their thread id (given by yappi)
threads = yappi.get_thread_stats()
for thread in threads:
    print(
        "Function stats for (%s) (%d)" % (thread.name, thread.id)
    )  # it is the Thread.__class__.__name__
    yappi.get_func_stats(ctx_id=thread.id,
                         filter_callback=lambda x: not x.full_name.endswith("Thread.run") and x.ttot > 0.01).strip_dirs().print_all()
    print()