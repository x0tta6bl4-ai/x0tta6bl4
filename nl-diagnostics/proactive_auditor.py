#!/usr/bin/env python3

import logging
import os
import shutil
import socket
import subprocess
import time

CHECK_PORTS = [443, 2083, 39829]
LOG_FILE = '/var/log/x0tta6bl4_audit.log'
STATE_DIR = '/var/lib/x0tta6bl4-audit'
RESTART_COOLDOWN_SEC = 1800
MAX_LOAD_PER_CPU = 4.0
DRY_RUN = os.environ.get('X0TTA_AUDIT_DRY_RUN') == '1'

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')


def ensure_state_dir():
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
    except OSError as exc:
        logging.info('state_dir_unavailable path=%s error=%s', STATE_DIR, exc)


def command_output(command, timeout=20):
    if DRY_RUN:
        logging.info('dry_run command=%s', ' '.join(command))
        return 0, '', ''

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
        return (
            result.returncode,
            result.stdout.decode(errors='replace'),
            result.stderr.decode(errors='replace'),
        )
    except subprocess.TimeoutExpired as exc:
        logging.info('command_timeout command=%s timeout=%s', ' '.join(command), exc.timeout)
        return 124, '', str(exc)
    except OSError as exc:
        logging.info('command_failed command=%s error=%s', ' '.join(command), exc)
        return 127, '', str(exc)


def host_is_overloaded():
    try:
        load_1m = os.getloadavg()[0]
    except OSError as exc:
        logging.info('load_check_unavailable error=%s', exc)
        return False

    cpu_count = os.cpu_count() or 1
    limit = cpu_count * MAX_LOAD_PER_CPU
    if load_1m > limit:
        logging.info('skip_restart reason=host_overloaded load_1m=%.2f limit=%.2f', load_1m, limit)
        return True
    return False


def restart_allowed(service, reason):
    ensure_state_dir()
    if host_is_overloaded():
        return False

    stamp_path = os.path.join(STATE_DIR, service.replace('/', '_') + '.restart.stamp')
    now = time.time()
    try:
        last_restart = os.path.getmtime(stamp_path)
    except OSError:
        last_restart = 0

    age = now - last_restart
    if age < RESTART_COOLDOWN_SEC:
        logging.info(
            'skip_restart service=%s reason=%s cooldown_left_sec=%d',
            service,
            reason,
            int(RESTART_COOLDOWN_SEC - age),
        )
        return False

    if not DRY_RUN:
        try:
            with open(stamp_path, 'w') as stamp:
                stamp.write(str(int(now)))
        except OSError as exc:
            logging.info('restart_stamp_failed service=%s path=%s error=%s', service, stamp_path, exc)
    return True


def controlled_restart(service, reason):
    if not restart_allowed(service, reason):
        return False

    logging.info('restart service=%s reason=%s', service, reason)
    returncode, _, stderr = command_output(['systemctl', 'restart', service], timeout=90)
    if returncode != 0:
        logging.info('restart_failed service=%s returncode=%s stderr=%s', service, returncode, stderr.strip())
        return False
    return True


def cleanup_forensics_if_needed():
    _, _, free = shutil.disk_usage('/')
    if (free / 1024**3) < 5:
        forensics_dir = '/var/log/forensics'
        if not os.path.isdir(forensics_dir):
            return

        logging.info('low_disk_free_gb=%.2f cleanup_dir=%s', free / 1024**3, forensics_dir)
        for entry in os.listdir(forensics_dir):
            path = os.path.join(forensics_dir, entry)
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except OSError as exc:
                logging.info('cleanup_failed path=%s error=%s', path, exc)


def check_warp():
    returncode, stdout, stderr = command_output(['warp-cli', '--accept-tos', 'status'], timeout=20)
    status_text = stdout + stderr
    if returncode == 0 and 'Connected' in status_text:
        return

    reason = 'warp status not connected'
    if returncode != 0:
        reason = 'warp status command failed'

    if controlled_restart('warp-svc', reason):
        command_output(['warp-cli', '--accept-tos', 'connect'], timeout=30)


def local_port_open(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            return sock.connect_ex(('127.0.0.1', port)) == 0
    except OSError as exc:
        logging.info('port_check_failed port=%s error=%s', port, exc)
        return False


def check_ports():
    missing_ports = []
    for port in CHECK_PORTS:
        if not local_port_open(port):
            missing_ports.append(port)

    if missing_ports:
        controlled_restart('x-ui', 'missing local ports: ' + ','.join(str(port) for port in missing_ports))


def main():
    cleanup_forensics_if_needed()
    check_warp()
    check_ports()


if __name__ == '__main__':
    main()
