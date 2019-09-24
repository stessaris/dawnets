#!/usr/bin/env python

import cpuinfo
import datetime
import logging
import os
import pprint as pp
import psutil
import re
import signal
import subprocess
import threading
try:
    import resource
except Exception:
    # not available on this system
    logging.warning('Cannot load resource package')


def set_memlimit(memory, name=None):
    try:
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    except (resource.error, ValueError) as e:
        logging.warning('Cannot set memory limits for process {}: {}'.format(name if name else os.getpid(), e))


class Runner:
    RUSAGE_KEYS = {
        "ru_utime": "time in user mode (float)",
        "ru_stime": "time in system mode (float)",
        "ru_maxrss": "maximum resident set size",
        "ru_ixrss": "shared memory size",
        "ru_idrss": "unshared memory size",
        "ru_isrss": "unshared stack size",
        "ru_minflt": "page faults not requiring I/O",
        "ru_majflt": "page faults requiring I/O",
        "ru_nswap": "number of swap outs",
        "ru_inblock": "block input operations",
        "ru_oublock": "block output operations",
        "ru_msgsnd": "messages sent",
        "ru_msgrcv": "messages received",
        "ru_nsignals": "signals received",
        "ru_nvcsw": "voluntary context switches",
        "ru_nivcsw": "involuntary context switches",
    }

    @staticmethod
    def hwinfo():
        info = cpuinfo.get_cpu_info()
        hwinfo = '{}, Memory: {}, Swap: {}'.format(
            re.sub(r'\s+', ' ', info['brand']),
            psutil.virtual_memory().total,
            psutil.swap_memory().total)
        return hwinfo

    @staticmethod
    def osinfo():
        uname = os.uname()
        return '{}, {}'.format(uname[0], uname[3])

    @staticmethod
    def sysload():
        try:
            return os.getloadavg()
        except OSError:
            return None

    @staticmethod
    def kill_proc_tree(proc, sig=signal.SIGTERM, include_parent=True,
                       timeout=3, on_terminate=None):
        # type: (psutil.Process, int, bool, int, ) -> Tuple[Iterable[Any], Iterable[Any]]
        """Kill a process tree (including grandchildren) with signal
        "sig" and return a (gone, still_alive) tuple.
        "on_terminate", if specified, is a callabck function which is
        called as soon as a child terminates.
        """
        try:
            children = proc.children(recursive=True)
            if include_parent:
                children.append(proc)
            for p in children:
                p.send_signal(sig)
            gone, alive = psutil.wait_procs(children, timeout=timeout,
                                            callback=on_terminate)
            return (gone, alive)
        except psutil.NoSuchProcess:
            return ([], [])

    @staticmethod
    def set_memlimit(memory, name=None):
        set_memlimit(memory, name=name)

    @staticmethod
    def run_with_timeout(cmd, timeout=None, cwd=None, memlimit=None):

        proc = psutil.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False,
            cwd=cwd,
            preexec_fn=(lambda: set_memlimit(memlimit, name=cmd[0])) if memlimit else None)

        timer_running = threading.Lock()

        def timer_func():
            with timer_running:
                Runner.kill_proc_tree(proc)

        timer = threading.Timer(timeout, timer_func) if timeout else None

        try:
            if timer:
                timer.start()

            initial_time = datetime.datetime.now()
            try:
                initial_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            except Exception:
                logging.error('Cannot query system resources, no profiling available')
                initial_usage = None

            (outdata, outerr) = proc.communicate()

            real_time = datetime.datetime.now() - initial_time
            delta_usage = resource.struct_rusage(
                f1 - f0 for f0, f1 in zip(initial_usage, resource.getrusage(resource.RUSAGE_CHILDREN))
            ) if initial_usage else None
            exitstatus = proc.wait(1)
        finally:
            if timer:
                # wait for the timer if it's running
                with timer_running:
                    timeout_happened = timer.finished.is_set()
                    # timeout_happened = real_time.total_seconds() > timeout
                    timer.cancel()
            else:
                timeout_happened = False

        # collect relevant statistics
        stats = {
            'command': cmd,
            'exit_status': exitstatus,
            'timeout_happened': timeout_happened,
            'timeout': timeout,
            'rtime': real_time.total_seconds(),
            'workdir': os.getcwd() if cwd is None else cwd,
            'stdout': outdata.decode(encoding='utf-8') if outdata is not None else '',
            'stderr': outerr.decode(encoding='utf-8') if outerr is not None else '',
            'hwinfo': Runner.hwinfo(),
            'osinfo': Runner.osinfo(),
            'sysload': Runner.sysload()

        }
        # get relevant keys from rusage
        for k in ('ru_utime', 'ru_stime', 'ru_maxrss', 'ru_ixrss', 'ru_idrss', 'ru_isrss', 'ru_inblock', 'ru_oublock'):
            stats[k] = getattr(delta_usage, k)

        return stats


def main():
    command_ptn = "echo 'Process {0} started'; sleep {1}; echo 'Process {0} finished' 1>&2"
    pp.pprint(Runner.run_with_timeout(['/bin/bash', '-c', command_ptn.format(1, 2)], timeout=5))
    pp.pprint(Runner.run_with_timeout(['/bin/bash', '-c', command_ptn.format(2, 5)]))
    pp.pprint(Runner.run_with_timeout(['/bin/bash', '-c', command_ptn.format(3, 5)], timeout=2))
    pp.pprint(Runner.run_with_timeout(['/bin/bash', '-c', command_ptn.format(3, 5)], timeout=2, memlimit=100))
    cmd = ['/bin/rash', '-c', command_ptn.format(3, 5)]
    try:
        pp.pprint(Runner.run_with_timeout(cmd, timeout=2))
    except OSError as e:
        logging.error("Error running '{}': {}".format(cmd, e))


if __name__ == '__main__':
    main()
