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

int slog2f(slog2_buffer_t buffer, uint16_t code, uint8_t severity,
           const char *format, ...)
{
    va_list ap;
    struct timespec ts;

    (void)buffer;
    (void)code;
    (void)severity;

    clock_gettime(CLOCK_REALTIME, &ts);

    pthread_mutex_lock(&_slog_lock);
    fprintf(stdout, "%02ld:%02ld:%02ld.%06ld %d %lu ",
            (long)((ts.tv_sec / 3600) % 24),
            (long)((ts.tv_sec / 60) % 60),
            (long)(ts.tv_sec % 60),
            (long)(ts.tv_nsec / 1000),
            (int)getpid(),
            (unsigned long)pthread_self());
    va_start(ap, format);
    vfprintf(stdout, format, ap);
    va_end(ap);
    fprintf(stdout, "\n");
    fflush(stdout);
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
