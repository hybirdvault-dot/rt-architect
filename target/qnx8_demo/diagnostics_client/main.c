/*
 * diagnostics_client — low-priority diagnostics requests to brake_controller.
 *
 * Sends DIAG_REQ every 100 ms.  Together with telemetry_client this provides
 * the steady low-priority load that exposes the flawed brake_controller.
 */

#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <pthread.h>
#include <sched.h>

#include "rtarch_ipc.h"

#define PRIO        10
#define ITERATIONS  50
#define PERIOD_US   100000  /* 100 ms */

static volatile sig_atomic_t _running = 1;

static void _on_signal(int sig)
{
    (void)sig;
    _running = 0;
}

static void _set_priority(int prio)
{
    struct sched_param sp;

    memset(&sp, 0, sizeof(sp));
    sp.sched_priority = prio;
    (void)pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp);
}

int main(int argc, char **argv)
{
    int server_pid = 0;
    int coid;
    uint64_t trace_id = 3000;
    uint32_t msg_id = 0;

    const char *log_name;

    if (argc < 2) {
        fprintf(stderr, "usage: diagnostics_client <channel_name> [log_name]\n");
        return 2;
    }

    log_name = (argc > 2) ? argv[2] : argv[1];

    signal(SIGINT, _on_signal);
    signal(SIGTERM, _on_signal);

    _set_priority(PRIO);

    if (rtarch_init("diagnostics_client") < 0) {
        fprintf(stderr, "diagnostics_client: slog2 init failed\n");
        return 1;
    }

    coid = rtarch_open(argv[1], &server_pid);
    if (coid < 0) {
        fprintf(stderr, "diagnostics_client: connect to %s failed\n", argv[1]);
        return 1;
    }

    while (_running && msg_id < ITERATIONS) {
        rtarch_payload_t req;
        rtarch_reply_t rep;

        memset(&req, 0, sizeof(req));
        memset(&rep, 0, sizeof(rep));

        trace_id++;
        msg_id++;

        req.trace_id = trace_id;
        req.msg_id = msg_id;
        req.kind = RTARCH_KIND_DIAG;
        req.value = 0.0;

        rtarch_log_send(trace_id, msg_id,
                        getpid(), "diagnostics_client",
                        server_pid, log_name,
                        "DIAG_REQ", PRIO);

        if (MsgSend(coid, &req, sizeof(req), &rep, sizeof(rep)) < 0) {
            perror("diagnostics_client: MsgSend");
            break;
        }

        usleep(PERIOD_US);
    }

    printf("diagnostics_client: sent %u requests\n", msg_id);
    return 0;
}
