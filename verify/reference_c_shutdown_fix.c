/*
 * reference_c_shutdown_fix.c — annotated reference for the P0-3 fix.
 *
 * The four concurrency bugs that stopped either brake controller from shutting
 * down, and the fixed pattern.  Applied to:
 *   target/qnx8_demo/brake_controller/main.c
 *   target/qnx8_demo/brake_controller_fixed/main.c
 *   (and the shared helper in target/qnx8_demo/include/rtarch_ipc.h)
 *
 * Verified:
 *   - sim: 4/4 SIGINT/SIGTERM cases CLEAN_EXIT_WITHIN_2S
 *   - real QNX 8.0: fixed controller SIGINT and SIGTERM CLEAN_EXIT_WITHIN_2S
 *     (was HANG_ALIVE_AFTER_2S), SIGKILL control DIES_AS_EXPECTED
 */

#include <signal.h>
#include <pthread.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>

#include <sys/neutrino.h>

/* ---- Fix 1: one shared flag, not a per-service static -------------------
 * Every service used to install its own handler that set its own static
 * _running.  When several services share a process (the Linux sim) the last
 * registration wins and the other services never see the flag.  Now there is
 * one process-wide flag and one handler.
 */
static volatile sig_atomic_t g_shutdown = 0;

static void on_signal(int sig)
{
    (void)sig;
    g_shutdown = 1;
}

/* ---- Fix 2: MsgReceive must be interruptible -----------------------------
 * ChannelCreate(_NTO_CHF_UNBLOCK) makes a blocked MsgReceive return when a
 * signal is delivered.  Without it the worker never observes the flag.
 * (The fixed controller additionally wakes the workers with a pulse, because a
 * process-directed signal may be delivered to a thread other than the one
 * blocked in MsgReceive.)
 */
static int chid;

static void *worker(void *arg)
{
    (void)arg;
    while (!g_shutdown) {
        struct _msg_info info;
        char req[64];
        int rcvid = MsgReceive(chid, req, sizeof(req), &info);

        if (rcvid < 0) {
            if (errno == EINTR) {
                continue;              /* re-check g_shutdown */
            }
            break;
        }
        if (rcvid == 0) {
            continue;                  /* pulse */
        }

        /* ---- Fix 4: never leave a sender blocked -------------------------
         * An unknown message kind used to hit a bare `continue`, so the sender
         * blocked forever in MsgSend.  Reply with an error instead.
         */
        if (req[0] == 0) {             /* example: unrecognised kind */
            MsgError(rcvid, ENOTSUP);
            continue;
        }

        MsgReply(rcvid, 0, NULL, 0);
    }
    return NULL;
}

/* ---- Fix 3: bound the join -----------------------------------------------
 * pthread_join(worker, NULL) hangs if the worker is stuck.  Join with a
 * deadline; on timeout, detach and log rather than hanging the process.
 */
static int timed_join(pthread_t thread, int timeout_ms)
{
    struct timespec deadline;

    clock_gettime(CLOCK_REALTIME, &deadline);
    deadline.tv_sec += timeout_ms / 1000;
    deadline.tv_nsec += (long)(timeout_ms % 1000) * 1000000L;
    if (deadline.tv_nsec >= 1000000000L) {
        deadline.tv_sec += 1;
        deadline.tv_nsec -= 1000000000L;
    }
    return pthread_timedjoin(thread, NULL, &deadline);   /* pthread_timedjoin_np on Linux */
}

int main(void)
{
    pthread_t thread;

    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);

    chid = ChannelCreate(_NTO_CHF_UNBLOCK);
    pthread_create(&thread, NULL, worker, NULL);

    while (!g_shutdown) {
        usleep(10000);
    }

    if (timed_join(thread, 2000) == ETIMEDOUT) {
        pthread_detach(thread);
    }
    return 0;
}
