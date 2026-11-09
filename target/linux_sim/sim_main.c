/*
 * Simulation harness: runs the real QNX service sources as threads in a
 * single Linux process, using the shim in shim.c for QNX IPC, the name space
 * and slog2.
 *
 * Usage:  rtarch_sim [flawed|fixed]     (default: flawed)
 *
 *   flawed -> brake_controller on one channel
 *   fixed  -> brake_controller_fixed on rtarch/brake_fast + rtarch/brake_slow
 *
 * Output (slog2-style lines) goes to stdout and is redirected to a log file by
 * run_sim.sh / run_fixed_sim.sh.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <pthread.h>
#include <unistd.h>

#include <sys/neutrino.h>
#include <sys/slog2.h>

extern int sensor_service_entry(int argc, char **argv);
extern int perception_service_entry(int argc, char **argv);
extern int brake_controller_entry(int argc, char **argv);
extern int brake_controller_fixed_entry(int argc, char **argv);
extern int telemetry_client_entry(int argc, char **argv);
extern int diagnostics_client_entry(int argc, char **argv);

typedef void *(*thread_fn)(void *);

static void *run_sensor(void *arg)
{
    char *argv[] = { "sensor_service", "perception_service", NULL };
    (void)arg;
    return (void *)(long)sensor_service_entry(2, argv);
}

static void *run_perception_flawed(void *arg)
{
    char *argv[] = { "perception_service", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)perception_service_entry(2, argv);
}

static void *run_perception_fixed(void *arg)
{
    char *argv[] = { "perception_service", "brake_fast", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)perception_service_entry(3, argv);
}

static void *run_brake_flawed(void *arg)
{
    (void)arg;
    return (void *)(long)brake_controller_entry(0, NULL);
}

static void *run_brake_fixed(void *arg)
{
    (void)arg;
    return (void *)(long)brake_controller_fixed_entry(0, NULL);
}

static void *run_telemetry_flawed(void *arg)
{
    char *argv[] = { "telemetry_client", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)telemetry_client_entry(2, argv);
}

static void *run_telemetry_fixed(void *arg)
{
    char *argv[] = { "telemetry_client", "brake_slow", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)telemetry_client_entry(3, argv);
}

static void *run_diagnostics_flawed(void *arg)
{
    char *argv[] = { "diagnostics_client", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)diagnostics_client_entry(2, argv);
}

static void *run_diagnostics_fixed(void *arg)
{
    char *argv[] = { "diagnostics_client", "brake_slow", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)diagnostics_client_entry(3, argv);
}

int main(int argc, char **argv)
{
    pthread_t threads[5];
    thread_fn server[2];
    thread_fn clients[3];
    int i;
    int fixed;

    fixed = (argc > 1 && strcmp(argv[1], "fixed") == 0);

    if (fixed) {
        server[0] = run_brake_fixed;
        server[1] = run_perception_fixed;
        clients[0] = run_sensor;
        clients[1] = run_telemetry_fixed;
        clients[2] = run_diagnostics_fixed;
        printf("sim: running FIXED brake_controller\n");
    } else {
        server[0] = run_brake_flawed;
        server[1] = run_perception_flawed;
        clients[0] = run_sensor;
        clients[1] = run_telemetry_flawed;
        clients[2] = run_diagnostics_flawed;
        printf("sim: running FLAWED brake_controller\n");
    }

    pthread_create(&threads[0], NULL, server[0], NULL);
    pthread_create(&threads[1], NULL, server[1], NULL);

    /* Give the servers a moment to publish their channels. */
    usleep(200000);

    for (i = 0; i < 3; i++) {
        pthread_create(&threads[2 + i], NULL, clients[i], NULL);
    }

    /* Wait for the clients to finish their iteration counts. */
    for (i = 2; i < 5; i++) {
        pthread_join(threads[i], NULL);
    }

    /*
     * Ask the servers to stop.  Each service has its own static _running
     * flag, so a shared SIGINT handler cannot reach all of them; setting
     * sim_shutdown unblocks MsgReceive and the process exit below reaps any
     * thread that is still finishing a message.
     */
    sim_shutdown = 1;
    raise(SIGINT);
    usleep(300000);

    sim_flush_log();
    printf("sim: all services finished\n");
    return 0;
}
