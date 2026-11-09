/*
 * Host-side simulation of the QNX 8.0 IPC and slog2 APIs.
 *
 * The service sources under target/qnx8_demo/ are compiled unmodified against
 * the shim headers in this directory.  This lets the whole pipeline (C event
 * generation -> RTARCH log -> Python parser -> rule engine -> report) be
 * exercised on Linux before the real QNX 8.0 target is available.
 *
 * NOTE: this is NOT QNX.  It is a functional simulation used for host-side
 * validation only.  Real QNX evidence requires running on the QEMU target.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <time.h>
#include <unistd.h>
#include <pthread.h>
#include <errno.h>

#include <sys/slog2.h>
#include <sys/neutrino.h>
#include <sys/netmgr.h>
#include <sys/iofunc.h>
#include <sys/dispatch.h>

/* ------------------------------------------------------------------ */
/*  slog2                                                             */
/* ------------------------------------------------------------------ */

static pthread_mutex_t _slog_lock = PTHREAD_MUTEX_INITIALIZER;

int slog2_register(slog2_buffer_set_config_t *config,
                   slog2_buffer_t *handles, uint32_t flags)
{
    static struct slog2_buffer_handle handle;

    (void)config;
    (void)flags;

    if (handles == NULL) {
        return -1;
    }
    handles[0] = &handle;
    return 0;
}

int slog2_reset(void)
{
    return 0;
}

/*
 * The real slog2 writes into a memory buffer that slog2info later dumps.  The
 * simulation does exactly the same: events are appended to a large in-memory
 * buffer and written out at exit.  This keeps file I/O out of the measured
 * critical path, which matters because the analysis is timing-sensitive.
 */
#define SIM_LOG_BUFFER_SIZE (4 * 1024 * 1024)
#define SIM_LOG_LINE_MAX    512

static char _sim_log[SIM_LOG_BUFFER_SIZE];
static size_t _sim_log_len = 0;

void sim_flush_log(void)
{
    if (_sim_log_len > 0) {
        fwrite(_sim_log, 1, _sim_log_len, stdout);
        fflush(stdout);
        _sim_log_len = 0;
    }
}

int slog2f(slog2_buffer_t buffer, uint16_t code, uint8_t severity,
           const char *format, ...)
{
    va_list ap;
    struct timespec ts;
    char line[SIM_LOG_LINE_MAX];
    size_t n = 0;
    int written;

    (void)buffer;
    (void)code;
    (void)severity;

    clock_gettime(CLOCK_REALTIME, &ts);

    written = snprintf(line, sizeof(line),
                       "%02ld:%02ld:%02ld.%06ld %d %lu ",
                       (long)((ts.tv_sec / 3600) % 24),
                       (long)((ts.tv_sec / 60) % 60),
                       (long)(ts.tv_sec % 60),
                       (long)(ts.tv_nsec / 1000),
                       (int)getpid(),
                       (unsigned long)pthread_self());
    if (written < 0) {
        return 0;
    }
    n = (size_t)written;
    if (n >= sizeof(line)) {
        n = sizeof(line) - 1;
    }

    va_start(ap, format);
    written = vsnprintf(line + n, sizeof(line) - n, format, ap);
    va_end(ap);
    if (written < 0) {
        return 0;
    }
    if (n + (size_t)written >= sizeof(line)) {
        n = sizeof(line) - 1;
    } else {
        n += (size_t)written;
    }
    line[n++] = '\n';

    pthread_mutex_lock(&_slog_lock);
    if (_sim_log_len + n < sizeof(_sim_log)) {
        memcpy(_sim_log + _sim_log_len, line, n);
        _sim_log_len += n;
    }
    pthread_mutex_unlock(&_slog_lock);

    return 0;
}

/* ------------------------------------------------------------------ */
/*  QNX synchronous message passing                                    */
/* ------------------------------------------------------------------ */

#define MAX_CHANNELS 16
#define MAX_PENDING  128
#define MAX_SLOTS    16
#define MAX_PAYLOAD  512

typedef struct {
    unsigned int sender_slot;
    pid_t sender_pid;
    size_t len;
    unsigned char payload[MAX_PAYLOAD];
} sim_msg_t;

typedef struct {
    sim_msg_t msgs[MAX_PENDING];
    int head;
    int tail;
    int count;
    pthread_mutex_t lock;
    pthread_cond_t avail;
    int used;
} sim_channel_t;

typedef struct {
    int used;
    pthread_t owner;
    pthread_mutex_t lock;
    pthread_cond_t done;
    int ready;
    int status;
    size_t len;
    unsigned char data[MAX_PAYLOAD];
} sim_slot_t;

static sim_channel_t _channels[MAX_CHANNELS];
static int _channel_count = 0;
static pthread_mutex_t _channels_lock = PTHREAD_MUTEX_INITIALIZER;

static sim_slot_t _slots[MAX_SLOTS];
static pthread_mutex_t _slots_lock = PTHREAD_MUTEX_INITIALIZER;

int sim_shutdown = 0;

int ChannelCreate(unsigned flags)
{
    int chid;

    (void)flags;

    pthread_mutex_lock(&_channels_lock);
    if (_channel_count >= MAX_CHANNELS) {
        pthread_mutex_unlock(&_channels_lock);
        return -1;
    }
    chid = _channel_count++;
    pthread_mutex_unlock(&_channels_lock);

    memset(&_channels[chid], 0, sizeof(sim_channel_t));
    pthread_mutex_init(&_channels[chid].lock, NULL);
    pthread_cond_init(&_channels[chid].avail, NULL);
    _channels[chid].used = 1;

    return chid;
}

int ChannelDestroy(int chid)
{
    if (chid < 0 || chid >= _channel_count) {
        return -1;
    }
    _channels[chid].used = 0;
    return 0;
}

int ConnectAttach(uint32_t nd, pid_t pid, int chid, unsigned index,
                  unsigned flags)
{
    (void)nd;
    (void)pid;
    (void)index;
    (void)flags;

    if (chid < 0 || chid >= _channel_count || !_channels[chid].used) {
        return -1;
    }
    /* Single-process simulation: the connection id is the channel id. */
    return chid;
}

int ConnectDetach(int coid)
{
    (void)coid;
    return 0;
}

static int _acquire_slot(void)
{
    pthread_t self = pthread_self();
    int i;
    int idx = -1;

    pthread_mutex_lock(&_slots_lock);

    for (i = 0; i < MAX_SLOTS; i++) {
        if (_slots[i].used && pthread_equal(_slots[i].owner, self)) {
            idx = i;
            break;
        }
    }

    if (idx < 0) {
        for (i = 0; i < MAX_SLOTS; i++) {
            if (!_slots[i].used) {
                idx = i;
                _slots[i].used = 1;
                _slots[i].owner = self;
                pthread_mutex_init(&_slots[i].lock, NULL);
                pthread_cond_init(&_slots[i].done, NULL);
                break;
            }
        }
    }

    pthread_mutex_unlock(&_slots_lock);

    if (idx >= 0) {
        pthread_mutex_lock(&_slots[idx].lock);
        _slots[idx].ready = 0;
        pthread_mutex_unlock(&_slots[idx].lock);
    }

    return idx;
}

long MsgSend(int coid, const void *smsg, size_t sbytes,
             void *rmsg, size_t rbytes)
{
    sim_channel_t *ch;
    sim_slot_t *slot;
    sim_msg_t *m;
    int idx;

    if (coid < 0 || coid >= _channel_count) {
        return -1;
    }

    idx = _acquire_slot();
    if (idx < 0) {
        return -1;
    }

    slot = &_slots[idx];
    ch = &_channels[coid];

    pthread_mutex_lock(&ch->lock);
    while (ch->count >= MAX_PENDING) {
        pthread_mutex_unlock(&ch->lock);
        usleep(1000);
        pthread_mutex_lock(&ch->lock);
    }

    m = &ch->msgs[ch->tail];
    m->sender_slot = (unsigned int)idx;
    m->sender_pid = getpid();
    m->len = (sbytes > MAX_PAYLOAD) ? MAX_PAYLOAD : sbytes;
    if (smsg != NULL && m->len > 0) {
        memcpy(m->payload, smsg, m->len);
    }

    ch->tail = (ch->tail + 1) % MAX_PENDING;
    ch->count++;
    pthread_cond_signal(&ch->avail);
    pthread_mutex_unlock(&ch->lock);

    /* Block until the server replies, exactly like QNX MsgSend. */
    pthread_mutex_lock(&slot->lock);
    while (!slot->ready) {
        pthread_cond_wait(&slot->done, &slot->lock);
    }
    if (rmsg != NULL && rbytes > 0) {
        size_t n = (rbytes < slot->len) ? rbytes : slot->len;
        memcpy(rmsg, slot->data, n);
    }
    pthread_mutex_unlock(&slot->lock);

    return (long)slot->status;
}

/*
 * Brief pause used by the busy-poll below.
 */
static inline void _sim_relax(void)
{
#if defined(__x86_64__) || defined(__i386__)
    __asm__ __volatile__("pause" ::: "memory");
#elif defined(__aarch64__)
    __asm__ __volatile__("yield" ::: "memory");
#else
    volatile unsigned int sink = 0;
    sink++;
    (void)sink;
#endif
}

int MsgReceive(int chid, void *rmsg, size_t rbytes, struct _msg_info *info)
{
    sim_channel_t *ch;
    sim_msg_t *m;
    int rcvid;

    if (chid < 0 || chid >= _channel_count) {
        return -1;
    }

    ch = &_channels[chid];

    pthread_mutex_lock(&ch->lock);
    while (ch->count == 0) {
        struct timespec ts;

        clock_gettime(CLOCK_REALTIME, &ts);
        ts.tv_nsec += 100L * 1000L * 1000L;   /* 100 ms */
        if (ts.tv_nsec >= 1000000000L) {
            ts.tv_sec++;
            ts.tv_nsec -= 1000000000L;
        }

        if (pthread_cond_timedwait(&ch->avail, &ch->lock, &ts) == ETIMEDOUT
            && sim_shutdown) {
            pthread_mutex_unlock(&ch->lock);
            errno = EINTR;
            return -1;
        }
    }

    m = &ch->msgs[ch->head];
    ch->head = (ch->head + 1) % MAX_PENDING;
    ch->count--;

    if (rmsg != NULL && rbytes > 0) {
        size_t n = (rbytes < m->len) ? rbytes : m->len;
        memcpy(rmsg, m->payload, n);
    }

    if (info != NULL) {
        memset(info, 0, sizeof(*info));
        info->pid = (int)m->sender_pid;
        info->chid = chid;
    }

    rcvid = (int)m->sender_slot;
    pthread_mutex_unlock(&ch->lock);

    return rcvid;
}

/* ------------------------------------------------------------------ */
/*  QNX name space (name_attach / name_open)                           */
/* ------------------------------------------------------------------ */

#define MAX_NAMES 16
#define MAX_NAME_LEN 128

static struct {
    char name[MAX_NAME_LEN];
    int chid;
    int used;
} _names[MAX_NAMES];
static int _name_count = 0;
static pthread_mutex_t _names_lock = PTHREAD_MUTEX_INITIALIZER;

name_attach_t *name_attach(dispatch_t *dpp, const char *path, unsigned flags)
{
    name_attach_t *att;
    int chid;
    int slot;

    (void)dpp;
    (void)flags;

    chid = ChannelCreate(0);
    if (chid < 0) {
        return NULL;
    }

    pthread_mutex_lock(&_names_lock);
    if (_name_count >= MAX_NAMES) {
        pthread_mutex_unlock(&_names_lock);
        return NULL;
    }
    slot = _name_count++;
    snprintf(_names[slot].name, sizeof(_names[slot].name), "%s", path);
    _names[slot].chid = chid;
    _names[slot].used = 1;
    pthread_mutex_unlock(&_names_lock);

    att = malloc(sizeof(*att));
    if (att == NULL) {
        return NULL;
    }
    att->dpp = NULL;
    att->chid = chid;
    att->mntid = 0;
    att->zero[0] = 0;
    att->zero[1] = 0;

    return att;
}

int name_open(const char *name, int flags)
{
    int coid = -1;
    int i;

    (void)flags;

    pthread_mutex_lock(&_names_lock);
    for (i = 0; i < _name_count; i++) {
        if (_names[i].used && strcmp(_names[i].name, name) == 0) {
            coid = _names[i].chid;
            break;
        }
    }
    pthread_mutex_unlock(&_names_lock);

    return coid;
}

int name_detach(name_attach_t *attach, unsigned flags)
{
    (void)attach;
    (void)flags;
    return 0;
}

int MsgReply(int rcvid, int status, const void *rmsg, size_t rbytes)
{
    sim_slot_t *slot;

    if (rcvid < 0 || rcvid >= MAX_SLOTS || !_slots[rcvid].used) {
        return -1;
    }

    slot = &_slots[rcvid];

    pthread_mutex_lock(&slot->lock);
    slot->status = status;
    slot->len = (rbytes > MAX_PAYLOAD) ? MAX_PAYLOAD : rbytes;
    if (rmsg != NULL && slot->len > 0) {
        memcpy(slot->data, rmsg, slot->len);
    }
    slot->ready = 1;
    pthread_cond_signal(&slot->done);
    pthread_mutex_unlock(&slot->lock);

    return 0;
}
