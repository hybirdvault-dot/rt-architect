/*
 * brake_controller_fixed — the FIXED version of the demo service.
 *
 * Two independent threads on two independent named channels:
 *
 *   rtarch/brake_fast   prio 30   BRAKE_CMD only, replies immediately
 *   rtarch/brake_slow   prio 10   TELEMETRY_REQ / DIAG_REQ, bounded service
 *
 * Because the channels are separate, low-priority telemetry can no longer sit
 * in front of a brake command.  That removes the head-of-line blocking and the
 * bottleneck.
 *
 * The architectural single point of failure REMAINS: both threads live in one
 * process, so if brake_controller dies, the critical path dies with it.  That
 * is intentional — the fix is a thread split, not redundancy, and RTArchitect
 * should still report SPOF-001.  A tool that reports zero findings after every
 * fix is a rubber stamp.
 */

#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <pthread.h>
#include <sched.h>
#include <errno.h>
#include <string.h>

#include "rtarch_ipc.h"

#define FAST_PRIO       30
#define SLOW_PRIO       10

/*
 * Fast path replies immediately.  The slow path is deliberately bounded: the
 * bottleneck rule compares the node's worst-case processing against 50% of
 * the deadline, so an unbounded slow path would keep BOTTLENECK-001 alive even
 * though the critical path is now isolated from it.
 */
#define FAST_DELAY_MS   0
#define SLOW_DELAY_MS   0

struct path_ctx {
    int     chid;
    int     prio;
    int     delay_ms;
    const char *channel_name;
};

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

static void *_path_thread(void *arg)
{
    struct path_ctx *ctx = (struct path_ctx *)arg;

    _set_priority(ctx->prio);

    while (_running) {
        struct _msg_info info;
        rtarch_payload_t req;
        rtarch_reply_t rep;
        int rcvid;

        memset(&info, 0, sizeof(info));
        memset(&req, 0, sizeof(req));

        rcvid = MsgReceive(ctx->chid, &req, sizeof(req), &info);
        if (rcvid < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror(ctx->channel_name);
            break;
        }

        rtarch_log_recv(req.trace_id, req.msg_id,
                        info.pid, _client_name(req.kind),
                        getpid(), "brake_controller",
                        _msg_type(req.kind), ctx->prio);

        delay((unsigned int)ctx->delay_ms);

        memset(&rep, 0, sizeof(rep));
        rep.status = 0;

        rtarch_log_reply(req.trace_id, req.msg_id,
                         getpid(), "brake_controller",
                         info.pid, _client_name(req.kind),
                         _ack_type(req.kind), ctx->prio);

        if (MsgReply(rcvid, 0, &rep, sizeof(rep)) < 0) {
            perror(ctx->channel_name);
        }
    }

    return NULL;
}

int main(void)
{
    name_attach_t *fast;
    name_attach_t *slow;
    struct path_ctx fast_ctx;
    struct path_ctx slow_ctx;
    pthread_t fast_thread;
    pthread_t slow_thread;

    signal(SIGINT, _on_signal);
    signal(SIGTERM, _on_signal);

    if (rtarch_init("brake_controller") < 0) {
        fprintf(stderr, "brake_controller_fixed: slog2 init failed\n");
        return 1;
    }

    fast = name_attach(NULL, "rtarch/brake_fast", 0);
    if (fast == NULL) {
        perror("brake_controller_fixed: name_attach(rtarch/brake_fast)");
        return 1;
    }

    slow = name_attach(NULL, "rtarch/brake_slow", 0);
    if (slow == NULL) {
        perror("brake_controller_fixed: name_attach(rtarch/brake_slow)");
        return 1;
    }

    /*
     * Publish channel addresses so clients can discover the peer pid for
     * logging and fall back to a direct attach if the name is unavailable.
     */
    rtarch_write_addr("brake_fast", getpid(), fast->chid);
    rtarch_write_addr("brake_slow", getpid(), slow->chid);

    memset(&fast_ctx, 0, sizeof(fast_ctx));
    fast_ctx.chid = fast->chid;
    fast_ctx.prio = FAST_PRIO;
    fast_ctx.delay_ms = FAST_DELAY_MS;
    fast_ctx.channel_name = "brake_fast";

    memset(&slow_ctx, 0, sizeof(slow_ctx));
    slow_ctx.chid = slow->chid;
    slow_ctx.prio = SLOW_PRIO;
    slow_ctx.delay_ms = SLOW_DELAY_MS;
    slow_ctx.channel_name = "brake_slow";

    if (pthread_create(&fast_thread, NULL, _path_thread, &fast_ctx) != 0) {
        perror("brake_controller_fixed: pthread_create(fast)");
        return 1;
    }
    if (pthread_create(&slow_thread, NULL, _path_thread, &slow_ctx) != 0) {
        perror("brake_controller_fixed: pthread_create(slow)");
        return 1;
    }

    printf("brake_controller_fixed: fast chid %d, slow chid %d\n",
           fast->chid, slow->chid);

    pthread_join(fast_thread, NULL);
    pthread_join(slow_thread, NULL);

    return 0;
}
