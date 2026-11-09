#ifndef SIM_SYS_IOFUNC_H
#define SIM_SYS_IOFUNC_H

/*
 * Host-side simulation of the QNX 8.0 <sys/iofunc.h> name API.
 *
 * The name_attach_t layout matches the real QNX structure (verified against
 * the QNX 8.0 library reference).  name_attach() registers a channel in an
 * in-process name registry; name_open() resolves it.
 */

#include <sys/dispatch.h>

typedef struct _name_attach {
    dispatch_t *dpp;
    int chid;
    int mntid;
    int zero[2];
} name_attach_t;

name_attach_t *name_attach(dispatch_t *dpp, const char *path, unsigned flags);
int name_open(const char *name, int flags);
int name_detach(name_attach_t *attach, unsigned flags);

#endif /* SIM_SYS_IOFUNC_H */
