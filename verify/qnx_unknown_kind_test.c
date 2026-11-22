/*
 * qnx_unknown_kind_test.c — real-QNX check for the A2 fix.
 *
 * Sends an unknown message kind to a brake controller channel.  The controller
 * must answer with MsgError(rcvid, ENOTSUP) so the sender unblocks immediately
 * instead of hanging.  Build with qcc and run on the QNX 8.0 target:
 *
 *   qcc -Wall -Wextra -Werror -o rtarch_unknown_kind qnx_unknown_kind_test.c
 *   ./rtarch_unknown_kind rtarch/brake_fast
 */
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <sys/neutrino.h>
#include <sys/dispatch.h>
#include <sys/iofunc.h>

struct unknown_msg {
    unsigned int kind;
    unsigned int pad;
    unsigned long long payload;
};

int main(int argc, char **argv)
{
    const char *name = argc > 1 ? argv[1] : "rtarch/brake_fast";
    int srv;
    struct unknown_msg msg;
    struct timespec t0, t1;
    double ms;
    int rc;

    srv = name_open(name, 0);
    if (srv < 0) {
        fprintf(stderr, "name_open %s failed: %s\n", name, strerror(errno));
        return 2;
    }

    memset(&msg, 0, sizeof(msg));
    msg.kind = 99;                          /* unknown kind */

    clock_gettime(CLOCK_MONOTONIC, &t0);
    rc = MsgSend(srv, &msg, sizeof(msg), NULL, 0);
    clock_gettime(CLOCK_MONOTONIC, &t1);
    ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;

    if (rc == -1 && errno == ENOTSUP) {
        printf("UNKNOWN_KIND_TEST_RESULT %s ENOTSUP in %.3f ms\n", name, ms);
        return ms < 50.0 ? 0 : 1;
    }

    printf("UNKNOWN_KIND_TEST_RESULT %s UNEXPECTED rc=%d errno=%d (%s) in %.3f ms\n",
           name, rc, errno, strerror(errno), ms);
    return 1;
}
