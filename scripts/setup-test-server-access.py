#!/usr/bin/env python3
"""Store the authorized OA test server password in the local macOS Keychain."""
import getpass
import os
from pathlib import Path
import subprocess
import sys

SERVICE = 'codex.gambit-oa.test.ssh'
ACCOUNT = 'root@49.232.4.107:22'


def main():
    if sys.platform != 'darwin':
        raise SystemExit('此录入工具需要在你的 macOS 本机运行。')
    password = getpass.getpass(f'{ACCOUNT} 的 SSH 密码（输入不显示）：')
    if not password:
        raise SystemExit('未输入密码，未保存。')
    result = subprocess.run([
        '/usr/bin/security', 'add-generic-password', '-U',
        '-s', SERVICE, '-a', ACCOUNT, '-w', password,
        '-T', '/usr/bin/security',
    ], capture_output=True)
    password = None
    if result.returncode:
        # Never print subprocess diagnostics, which might contain credential material.
        raise SystemExit('保存到钥匙串失败；请确认登录钥匙串已解锁后重试。')
    root = Path(__file__).resolve().parents[1]
    path = root / '.env.remote-test.local'
    # Connection metadata only. This file is excluded from Git and Docker context.
    if not path.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write('OA_TEST_SSH_HOST=49.232.4.107\nOA_TEST_SSH_PORT=22\n'
                         'OA_TEST_SSH_USER=root\nOA_TEST_REMOTE_DIR=\n'
                         f'OA_TEST_KEYCHAIN_SERVICE={SERVICE}\nOA_TEST_KEYCHAIN_ACCOUNT={ACCOUNT}\n')
    # Remove the earlier one-session credential if the user had already entered it.
    temporary = Path('/private/tmp/gambit-oa-ssh-auth/password')
    if temporary.is_file():
        temporary.unlink()
    print('已保存到本机钥匙串，后续可直接连接。回到聊天回复“已保存”即可，无需发送密码。')


if __name__ == '__main__':
    main()
