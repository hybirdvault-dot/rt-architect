#ifndef SIM_SYS_NEUTRINO_H
#define SIM_SYS_NEUTRINO_H

/*
 * Host-side simulation of the QNX 8.0 <sys/neutrino.h> API.
 *
 * MsgSend / MsgReceive / MsgReply / ChannelCreate / ConnectAttach are
 * implemented over in-process condition-variable queues so the real service
 * sources compile and run unmodified on Linux.  This is a functional
 * simulation of QNX synchronous message passing, not a driver.
 */

#include <stddef.h>
#include <sys/types.h>
#include <stdint.h>
#include <unistd.h>

struct _msg_info {
    int pid;
    int tid;
    int chid;
    int coid;
    int rcvid;
    int priority;
    int flags;
};

/* Set by the simulation harness to unblock servers at shutdown. */
extern int sim_shutdown;

int ChannelCreate(unsigned flags);
int ChannelDestroy(int chid);
long MsgSend(int coid, const void *smsg, size_t sbytes,
             void *rmsg, size_t rbytes);
int MsgReceive(int chid, void *rmsg, size_t rbytes, struct _msg_info *info);
int MsgReply(int rcvid, int status, const void *rmsg, size_t rbytes);
int ConnectAttach(uint32_t nd, pid_t pid, int chid, unsigned index,
                  unsigned flags);
int ConnectDetach(int coid);

/*
 * QNX declares delay() in <unistd.h>; the simulation declares it here so the
 * real QNX headers are not shadowed.
 */
static inline unsigned int delay(unsigned int duration)
{
    usleep((useconds_t)duration * 1000u);
    return 0;
}

#endif /* SIM_SYS_NEUTRINO_H */
