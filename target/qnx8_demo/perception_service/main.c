/*
 * perception_service — server for sensor_service, client of brake_controller.
 *
 *   RECV SENSOR_FRAME  ->  log RECV
 *   process (2 ms)
 *   SEND BRAKE_CMD     ->  log SEND, MsgSend to brake
 *   REPLY SENSOR_ACK   ->  log REPLY, MsgReply to sensor
 *
 * Because the reply to the sensor is only sent after the brake round trip
 * completes, the measured "processing" time of this service includes the
 * brake latency.  That is exactly what we want the analysis to see.
 */

#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include <pthread.h>
#include <sched.h>
#include <errno.h>

#include "rtarch_ipc.h"

#define PRIO            25
#define PROCESS_US      2000   /* 2 ms perception algorithm */
#define BRAKE_PRIO      30

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
    int brake_pid = 0;
    int chid;
    int brake_coid;
    uint64_t forwarded_trace_id = 5000;
    uint32_t forwarded_msg_id = 0;

    const char *log_name;

    if (argc < 2) {
        fprintf(stderr, "usage: perception_service <channel_name> [log_name]\n");
        return 2;
    }

    log_name = (argc > 2) ? argv[2] : argv[1];

    signal(SIGINT, _on_signal);
    signal(SIGTERM, _on_signal);

    _set_priority(PRIO);

    if (rtarch_init("perception_service") < 0) {
        fprintf(stderr, "perception_service: slog2 init failed\n");
        return 1;
    }

    chid = ChannelCreate(0);
    if (chid < 0) {
        perror("perception_service: ChannelCreate");
        return 1;
    }

    if (rtarch_write_addr("perception_service", getpid(), chid) < 0) {
        fprintf(stderr, "perception_service: cannot publish address\n");
        return 1;
    }

    brake_coid = rtarch_open(argv[1], &brake_pid);
    if (brake_coid < 0) {
        fprintf(stderr, "perception_service: connect to %s failed\n", argv[1]);
        return 1;
    }

    while (_running) {
        struct _msg_info info;
        rtarch_payload_t req;
        rtarch_payload_t brake_req;
        rtarch_reply_t brake_rep;
        rtarch_reply_t rep;
        int rcvid;

        memset(&info, 0, sizeof(info));
        memset(&req, 0, sizeof(req));

        rcvid = MsgReceive(chid, &req, sizeof(req), &info);
        if (rcvid < 0) {
            if (errno == EINTR) {
                continue;
            }
            perror("perception_service: MsgReceive");
            break;
        }

        rtarch_log_recv(req.trace_id, req.msg_id,
                        info.pid, "sensor_service",
                        getpid(), "perception_service",
                        "SENSOR_FRAME", PRIO);

        usleep(PROCESS_US);

        memset(&brake_req, 0, sizeof(brake_req));
        memset(&brake_rep, 0, sizeof(brake_rep));

        /*
         * The host groups events into SEND/RECV/REPLY triples by
         * (trace_id, msg_id), so every hop needs its own pair.  This forward
         * is a brand-new request/reply exchange and gets a fresh trace_id from
         * a range disjoint from the sensor's, plus a fresh msg_id.  Reusing
         * the incoming pair would collapse the two hops into one triple.
         */
        brake_req.trace_id = ++forwarded_trace_id;
        brake_req.msg_id = ++forwarded_msg_id;
        brake_req.kind = RTARCH_KIND_BRAKE_CMD;
        brake_req.value = req.value;

        rtarch_log_send(brake_req.trace_id, brake_req.msg_id,
                        getpid(), "perception_service",
                        brake_pid, log_name,
                        "BRAKE_CMD", BRAKE_PRIO);

        if (MsgSend(brake_coid, &brake_req, sizeof(brake_req),
                    &brake_rep, sizeof(brake_rep)) < 0) {
            perror("perception_service: MsgSend(brake)");
        }

        memset(&rep, 0, sizeof(rep));
        rep.status = brake_rep.status;

        rtarch_log_reply(req.trace_id, req.msg_id,
                         getpid(), "perception_service",
                         info.pid, "sensor_service",
                         "SENSOR_ACK", PRIO);

        if (MsgReply(rcvid, 0, &rep, sizeof(rep)) < 0) {
            perror("perception_service: MsgReply");
        }
    }

    return 0;
}
