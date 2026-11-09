/*
 * sensor_service — periodic sensor frames to perception_service.
 *
 * Client only: logs SEND, then blocks in MsgSend until perception replies.
 */

#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <pthread.h>
#include <sched.h>

#include "rtarch_ipc.h"

#define PRIO            25
#define ITERATIONS      200
#define PERIOD_US       5000   /* 5 ms */

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
    /* Best effort: a real-time priority needs privileges we may not have. */
    (void)pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp);
}

int main(int argc, char **argv)
{
    int server_pid = 0;
    int coid;
    uint64_t trace_id = 1000;
    uint32_t msg_id = 0;

    const char *log_name;

    if (argc < 2) {
        fprintf(stderr, "usage: sensor_service <channel_name> [log_name]\n");
        return 2;
    }

    /* The channel name is used for connection; log_name is what appears in
     * the RTARCH events (it defaults to the channel name). */
    log_name = (argc > 2) ? argv[2] : argv[1];

    signal(SIGINT, _on_signal);
    signal(SIGTERM, _on_signal);

    _set_priority(PRIO);

    if (rtarch_init("sensor_service") < 0) {
        fprintf(stderr, "sensor_service: slog2 init failed\n");
        return 1;
    }

    coid = rtarch_open(argv[1], &server_pid);
    if (coid < 0) {
        fprintf(stderr, "sensor_service: connect to %s failed\n", argv[1]);
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
        req.kind = RTARCH_KIND_SENSOR_FRAME;
        req.value = 1.0;

        rtarch_log_send(trace_id, msg_id,
                        getpid(), "sensor_service",
                        server_pid, log_name,
                        "SENSOR_FRAME", PRIO);

        if (MsgSend(coid, &req, sizeof(req), &rep, sizeof(rep)) < 0) {
            perror("sensor_service: MsgSend");
            break;
        }

        usleep(PERIOD_US);
    }

    printf("sensor_service: sent %u frames\n", msg_id);
    return 0;
}
