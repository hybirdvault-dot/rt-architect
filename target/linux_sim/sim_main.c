/*
 * Simulation harness: runs the five real QNX service sources as threads in a
 * single Linux process, using the shim in shim.c for QNX IPC and slog2.
 *
 * Output (slog2-style lines) goes to stdout and is redirected to a log file by
 * run_sim.sh.
 */

#include <stdio.h>
#include <signal.h>
#include <pthread.h>

#include <sys/neutrino.h>

extern int sensor_service_entry(int argc, char **argv);
extern int perception_service_entry(int argc, char **argv);
extern int brake_controller_entry(int argc, char **argv);
extern int telemetry_client_entry(int argc, char **argv);
extern int diagnostics_client_entry(int argc, char **argv);

typedef void *(*thread_fn)(void *);

static void *run_sensor(void *arg)
{
    char *argv[] = { "sensor_service", "perception_service", NULL };
    (void)arg;
    return (void *)(long)sensor_service_entry(2, argv);
}

static void *run_perception(void *arg)
{
    char *argv[] = { "perception_service", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)perception_service_entry(2, argv);
}

static void *run_brake(void *arg)
{
    (void)arg;
    return (void *)(long)brake_controller_entry(0, NULL);
}

static void *run_telemetry(void *arg)
{
    char *argv[] = { "telemetry_client", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)telemetry_client_entry(2, argv);
}

static void *run_diagnostics(void *arg)
{
    char *argv[] = { "diagnostics_client", "brake_controller", NULL };
    (void)arg;
    return (void *)(long)diagnostics_client_entry(2, argv);
}

int main(void)
{
    pthread_t threads[5];
    thread_fn clients[3];
    int i;

    pthread_create(&threads[0], NULL, run_brake, NULL);
    pthread_create(&threads[1], NULL, run_perception, NULL);

    /* Give the servers a moment to publish their addresses. */
    usleep(200000);

    clients[0] = run_sensor;
    clients[1] = run_telemetry;
    clients[2] = run_diagnostics;
    for (i = 0; i < 3; i++) {
        pthread_create(&threads[2 + i], NULL, clients[i], NULL);
    }

    /* Wait for the clients to finish their iteration counts. */
    for (i = 2; i < 5; i++) {
        pthread_join(threads[i], NULL);
    }

    /*
     * Stop the servers.  Each service has its own static _running flag, so a
     * shared SIGINT handler cannot reach all of them; cancellation is the
     * reliable way to unblock threads sitting in MsgReceive.
     */
    sim_shutdown = 1;
    pthread_cancel(threads[0]);
    pthread_cancel(threads[1]);

    for (i = 0; i < 2; i++) {
        pthread_join(threads[i], NULL);
    }

    printf("sim: all services finished\n");
    return 0;
}
