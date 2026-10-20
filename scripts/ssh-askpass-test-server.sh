#!/bin/sh
# Used only by SSH_ASKPASS for the authorized OA test host; do not run to display the password.
exec /usr/bin/security find-generic-password \
  -s codex.gambit-oa.test.ssh \
  -a root@49.232.4.107:22 \
  -w
