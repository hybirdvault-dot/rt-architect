#ifndef SIM_SYS_SLOG2_H
#define SIM_SYS_SLOG2_H

/*
 * Host-side simulation of the QNX 8.0 <sys/slog2.h> API.
 *
 * The declarations mirror the real QNX 8.0 API exactly (verified against the
 * QNX 8.0 library reference).  The implementation writes to stdout with a
 * realistic slog2-style header so the Python parser's prefix tolerance is
 * exercised.
 */

#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>

#define SLOG2_MAX_BUFFERS 8

#define SLOG2_SHUTDOWN  0
#define SLOG2_CRITICAL  1
#define SLOG2_ERROR     2
#define SLOG2_WARNING   3
#define SLOG2_NOTICE    4
#define SLOG2_INFO      5
#define SLOG2_DEBUG1    6
#define SLOG2_DEBUG2    7

/* Opaque on real QNX; given a definition here so the shim can instantiate it. */
struct slog2_buffer_handle {
    int opaque;
};

typedef struct slog2_buffer_handle *slog2_buffer_t;

typedef struct {
    const char *buffer_name;
    int num_pages;
} slog2_buffer_config_t;

typedef struct {
    int num_buffers;
    const char *buffer_set_name;
    uint8_t verbosity_level;
    slog2_buffer_config_t buffer_config[SLOG2_MAX_BUFFERS];
    uint32_t max_retries;
} slog2_buffer_set_config_t;

int slog2_register(slog2_buffer_set_config_t *config,
                   slog2_buffer_t *handles, uint32_t flags);
int slog2_reset(void);
int slog2f(slog2_buffer_t buffer, uint16_t code, uint8_t severity,
           const char *format, ...);

#endif /* SIM_SYS_SLOG2_H */
