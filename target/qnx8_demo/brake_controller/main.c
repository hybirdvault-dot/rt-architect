/*
 * brake_controller — FLAWED demo service.
 *
 * FLAW: single-threaded, FIFO processing on one channel.  Every request is
 * handled in arrival order, and low-priority telemetry / diagnostics requests
 * take much longer to process than a high-priority brake command.
 *
 * Consequence: a high-priority BRAKE_CMD that arrives while a low-priority
 * request is being processed waits for the full low-priority service time.
 * That is classic head-of-line blocking / priority inversion.
 *
 * The delays below are the artificial flaw that makes the effect measurable
 * in the log.  Tune them to match the real target's timing.
 */

#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <pthread.h>
#include <sched.h>
#include <errno.h>

#include "rtarch_ipc.h"

#define PRIO                30
#define BRAKE_DELAY_MS      1   /* high-priority brake command service time  */
#define LOWPRIO_DELAY_MS    8   /* telemetry / diagnostics service time       */

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

static const char *_msg_type(uint32_t kind)
{
    switch (kind) {
    case RTARCH_KIND_BRAKE_CMD: return "BRAKE_CMD";
    case RTARCH_KIND_TELEMETRY: return "TELEMETRY_REQ";
    case RTARCH_KIND_DIAG:      return "DIAG_REQ";
    default:                    return "UNKNOWN";
    }
}

static const char *_ack_type(uint32_t kind)
{
    switch (kind) {
    case RTARCH_KIND_BRAKE_CMD: return "BRAKE_ACK";
    case RTARCH_KIND_TELEMETRY: return "TELEMETRY_ACK";
    case RTARCH_KIND_DIAG:      return "DIAG_ACK";
    default:                    return "UNKNOWN_ACK";
    }
}

static const char *_client_name(uint32_t kind)
{
    switch (kind) {
    case RTARCH_KIND_BRAKE_CMD: return "perception_service";
    case RTARCH_KIND_TELEMETRY: return "telemetry_client";
    case RTARCH_KIND_DIAG:      return "diagnostics_client";
    default:                    return "unknown";
    }
}

static int _prio(uint32_t kind)
{
    return (kind == RTARCH_KIND_BRAKE_CMD) ? 30 : 10;
}

int main(void)
{
    int chid;

    signal(SIGINT, _on_signal);
    signal(SIGTERM, _on_signal);

    _set_priority(PRIO);

    if (rtarch_init("brake_controller") < 0) {
        fprintf(stderr, "brake_controller: slog2 init failed\n");
        return 1;
    }

    chid = ChannelCreate(0);
    if (chid < 0) {
        perror("brake_controller: ChannelCreate");
        return 1;
    }

    if (rtarch_write_addr("brake_controller", getpid(), chid) < 0) {
        fprintf(stderr, "brake_controller: cannot publish address\n");
        return 1;
    }

    printf("brake_controller: listening on chid %d\n", chid);

    while (_running) {
        struct _msg_info info;
        rtarch_payload_t req;
        rtarch_reply_t rep;
        int rcvid;

        memset(&info, 0, sizeof(info));
        memset(&req, 0, sizeof(req));

        rcvid = MsgReceive(chid, &req, sizeof(req), &info);
        if (rcvid < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("brake_controller: MsgReceive");
            break;
        }

        rtarch_log_recv(req.trace_id, req.msg_id,
                        info.pid, _client_name(req.kind),
                        getpid(), "brake_controller",
                        _msg_type(req.kind), _prio(req.kind));

        /*
         * The flaw: a single thread processes requests one at a time, in
         * arrival order, with a long service time for low-priority work.
         */
        if (req.kind == RTARCH_KIND_BRAKE_CMD) {
            delay(BRAKE_DELAY_MS);
        } else {
            delay(LOWPRIO_DELAY_MS);
        }

        memset(&rep, 0, sizeof(rep));
        rep.status = 0;

        rtarch_log_reply(req.trace_id, req.msg_id,
                         getpid(), "brake_controller",
                         info.pid, _client_name(req.kind),
                         _ack_type(req.kind), _prio(req.kind));

        if (MsgReply(rcvid, 0, &rep, sizeof(rep)) < 0) {
            perror("brake_controller: MsgReply");
        }
    }

    return 0;
}
