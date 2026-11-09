#ifndef RTARCH_IPC_H
#define RTARCH_IPC_H

/*
 * RTArchitect — QNX 8.0 target instrumentation layer.
 *
 * Every service includes this header.  It provides:
 *   - one CLOCK_MONOTONIC clock helper (never slog2's own timestamp)
 *   - the slog2 buffer registration
 *   - rtarch_log_send/recv/reply, which emit the locked RTARCH v1 format
 *   - a tiny well-known-address-file helper so services can find each other
 *
 * The log line format is LOCKED and must match the Python parser:
 *
 *   RTARCH v=1 ts_ns=<ns> phase=<SEND|RECV|REPLY> trace_id=<id> msg_id=<id>
 *          src_pid=<pid> src_name=<svc> dst_pid=<pid> dst_name=<svc>
 *          msg_type=<type> prio=<prio>
 */

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <sys/slog2.h>
#include <sys/neutrino.h>
#include <sys/netmgr.h>
#include <sys/iofunc.h>
#include <sys/dispatch.h>

/* ------------------------------------------------------------------ */
/*  Payload                                                           */
/* ------------------------------------------------------------------ */

#define RTARCH_KIND_SENSOR_FRAME 1
#define RTARCH_KIND_BRAKE_CMD    2
#define RTARCH_KIND_TELEMETRY    3
#define RTARCH_KIND_DIAG         4

typedef struct {
    uint64_t trace_id;
    uint32_t msg_id;
    uint32_t kind;
    double   value;
} rtarch_payload_t;

typedef struct {
    int32_t status;
} rtarch_reply_t;

/* ------------------------------------------------------------------ */
/*  Clock — ONE clock source for ALL timestamps                        */
/* ------------------------------------------------------------------ */

static inline uint64_t rtarch_now_ns(void)
{
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

/* ------------------------------------------------------------------ */
/*  slog2 buffer                                                       */
/* ------------------------------------------------------------------ */

static slog2_buffer_t _rtarch_buf = NULL;

static inline int rtarch_init(const char *process_name)
{
    slog2_buffer_set_config_t cfg;

    memset(&cfg, 0, sizeof(cfg));
    cfg.buffer_set_name = process_name;
    cfg.num_buffers = 1;
    cfg.verbosity_level = SLOG2_INFO;
    cfg.buffer_config[0].buffer_name = "rtarch";
    cfg.buffer_config[0].num_pages = 4;
    cfg.max_retries = UINT32_MAX;

    (void)slog2_reset();

    if (slog2_register(&cfg, &_rtarch_buf, 0) != 0) {
        return -1;
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/*  Logging                                                           */
/* ------------------------------------------------------------------ */

static inline void rtarch_log(
    uint64_t trace_id, uint32_t msg_id, const char *phase,
    int src_pid, const char *src_name,
    int dst_pid, const char *dst_name,
    const char *msg_type, int prio)
{
    if (_rtarch_buf == NULL) {
        return;
    }

    slog2f(_rtarch_buf, 0, SLOG2_INFO,
           "RTARCH v=1 ts_ns=%llu phase=%s trace_id=%llu msg_id=%u "
           "src_pid=%d src_name=%s dst_pid=%d dst_name=%s msg_type=%s prio=%d",
           (unsigned long long)rtarch_now_ns(),
           phase,
           (unsigned long long)trace_id,
           (unsigned int)msg_id,
           src_pid, src_name,
           dst_pid, dst_name,
           msg_type, prio);
}

static inline void rtarch_log_send(
    uint64_t trace_id, uint32_t msg_id,
    int src_pid, const char *src_name,
    int dst_pid, const char *dst_name,
    const char *msg_type, int prio)
{
    rtarch_log(trace_id, msg_id, "SEND",
               src_pid, src_name, dst_pid, dst_name, msg_type, prio);
}

static inline void rtarch_log_recv(
    uint64_t trace_id, uint32_t msg_id,
    int src_pid, const char *src_name,
    int dst_pid, const char *dst_name,
    const char *msg_type, int prio)
{
    rtarch_log(trace_id, msg_id, "RECV",
               src_pid, src_name, dst_pid, dst_name, msg_type, prio);
}

static inline void rtarch_log_reply(
    uint64_t trace_id, uint32_t msg_id,
    int src_pid, const char *src_name,
    int dst_pid, const char *dst_name,
    const char *msg_type, int prio)
{
    rtarch_log(trace_id, msg_id, "REPLY",
               src_pid, src_name, dst_pid, dst_name, msg_type, prio);
}

/* ------------------------------------------------------------------ */
/*  Service discovery — servers publish "<pid> <chid>" in /tmp         */
/* ------------------------------------------------------------------ */

#define RTARCH_ADDR_FILE "/tmp/rtarch_%s.addr"

static inline int rtarch_write_addr(const char *service_name, int pid, int chid)
{
    char path[128];
    FILE *f;

    snprintf(path, sizeof(path), RTARCH_ADDR_FILE, service_name);
    f = fopen(path, "w");
    if (f == NULL) {
        return -1;
    }
    fprintf(f, "%d %d\n", pid, chid);
    fclose(f);
    return 0;
}

static inline int rtarch_read_addr(const char *service_name, int *pid, int *chid)
{
    char path[128];
    FILE *f;

    snprintf(path, sizeof(path), RTARCH_ADDR_FILE, service_name);
    f = fopen(path, "r");
    if (f == NULL) {
        return -1;
    }
    if (fscanf(f, "%d %d", pid, chid) != 2) {
        fclose(f);
        return -1;
    }
    fclose(f);
    return 0;
}

static inline int rtarch_wait_for_addr(
    const char *service_name, int *pid, int *chid, int timeout_ms)
{
    int waited = 0;

    while (waited < timeout_ms) {
        if (rtarch_read_addr(service_name, pid, chid) == 0) {
            return 0;
        }
        usleep(20000);
        waited += 20;
    }
    return -1;
}

/*
 * Open a named channel.  Prefers the QNX name space (name_open); if the name
 * is not resolvable, falls back to a direct ConnectAttach using the address
 * file.  Returns the connection id, or -1 on failure.
 *
 * When server_pid is non-NULL it receives the peer's pid (used for logging).
 */
static inline int rtarch_open(const char *channel_name, int *server_pid)
{
    int pid = 0;
    int chid = 0;
    int coid;

    /* Best-effort pid discovery for logging. */
    (void)rtarch_wait_for_addr(channel_name, &pid, &chid, 5000);
    if (server_pid != NULL) {
        *server_pid = pid;
    }

    coid = name_open(channel_name, 0);
    if (coid < 0) {
        char full[192];

        snprintf(full, sizeof(full), "/dev/name/local/%s", channel_name);
        coid = name_open(full, 0);
    }
    if (coid >= 0) {
        return coid;
    }

    /* Fallback: direct channel attach. */
    return ConnectAttach(ND_LOCAL_NODE, pid, chid, 0, 0);
}

/*
 * Connect to a named server.  Returns the connection id, or -1 on failure.
 * When server_pid is non-NULL it receives the peer's pid (used for logging).
 */
static inline int rtarch_connect(const char *service_name, int *server_pid)
{
    int pid = 0;
    int chid = 0;
    int coid;

    if (rtarch_wait_for_addr(service_name, &pid, &chid, 10000) < 0) {
        return -1;
    }

    coid = ConnectAttach(ND_LOCAL_NODE, pid, chid, 0, 0);
    if (coid < 0) {
        return -1;
    }

    if (server_pid != NULL) {
        *server_pid = pid;
    }
    return coid;
}

#endif /* RTARCH_IPC_H */
