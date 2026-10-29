"""Minimal service manager for PID 1: dependency-ordered start, one-shot and long-running services,
restart with a crash-loop limit, zombie reaping. No D-Bus, no sockets, no config language."""
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field


@dataclass
class Service:
    name: str
    argv: list
    after: list = field(default_factory=list)
    oneshot: bool = False
    env: dict = None
    # runtime state
    proc: subprocess.Popen = None
    status: str = "pending"      # pending | running | done | failed
    exit_code: int = None
    crashes: list = field(default_factory=list)


class Supervisor:
    MAX_CRASHES, WINDOW = 5, 30.0

    def __init__(self, services, log=print, clock=time.monotonic):
        self.svc = {s.name: s for s in services}
        self.log, self.clock = log, clock
        for s in services:
            for dep in s.after:
                if dep not in self.svc:
                    raise ValueError(f"{s.name}: unknown dependency {dep}")
        self.order = self._toposort()

    def _toposort(self):
        out, seen, temp = [], set(), set()
        def visit(n):
            if n in seen:
                return
            if n in temp:
                raise ValueError(f"dependency cycle at {n}")
            temp.add(n)
            for d in self.svc[n].after:
                visit(d)
            temp.discard(n); seen.add(n); out.append(n)
        for n in self.svc:
            visit(n)
        return out

    def _spawn(self, s):
        env = dict(os.environ, **(s.env or {}))
        s.proc = subprocess.Popen(s.argv, env=env, start_new_session=True)
        s.status = "running"
        self.log(f"service {s.name}: started pid={s.proc.pid}")

    def step(self):
        """One scheduling pass; returns True while anything is still pending or running."""
        for n in self.order:
            s = self.svc[n]
            if s.status == "pending" and all(self.svc[d].status == ("done" if self.svc[d].oneshot else "running")
                                             for d in s.after):
                if any(self.svc[d].status == "failed" for d in s.after):
                    s.status = "failed"
                    self.log(f"service {n}: not started, dependency failed")
                else:
                    self._spawn(s)
            elif s.status == "pending" and any(self.svc[d].status == "failed" for d in s.after):
                s.status = "failed"
                self.log(f"service {n}: not started, dependency failed")
        for s in self.svc.values():
            if s.status == "running" and s.proc.poll() is not None:
                s.exit_code = s.proc.returncode
                if s.oneshot:
                    s.status = "done" if s.exit_code == 0 else "failed"
                    self.log(f"service {s.name}: exited code={s.exit_code} -> {s.status}")
                else:
                    now = self.clock()
                    s.crashes = [t for t in s.crashes if now - t < self.WINDOW] + [now]
                    if len(s.crashes) >= self.MAX_CRASHES:
                        s.status = "failed"
                        self.log(f"service {s.name}: crash loop, giving up")
                    else:
                        self.log(f"service {s.name}: died code={s.exit_code}, restarting")
                        self._spawn(s)
        self._reap()
        return any(s.status == "pending" or (s.status == "running" and s.oneshot) for s in self.svc.values())

    @staticmethod
    def _reap():
        """Collect orphaned children (we are PID 1 in production)."""
        if os.getpid() != 1:
            return
        try:
            while os.waitpid(-1, os.WNOHANG)[0]:
                pass
        except ChildProcessError:
            pass

    def run_until_settled(self, timeout=120, poll=0.1):
        end = time.monotonic() + timeout
        while self.step():
            if time.monotonic() > end:
                raise TimeoutError("services did not settle")
            time.sleep(poll)

    def stop_all(self, grace=3.0):
        for s in reversed(self.order):
            p = self.svc[s].proc
            if p and p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
        end = time.monotonic() + grace
        for s in self.svc.values():
            if s.proc and s.proc.poll() is None:
                try:
                    s.proc.wait(max(0, end - time.monotonic()))
                except subprocess.TimeoutExpired:
                    os.killpg(s.proc.pid, signal.SIGKILL)
