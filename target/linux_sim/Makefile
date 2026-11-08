# Host-side simulation build.
#
# Compiles the REAL service sources from target/qnx8_demo/ against the shim
# headers in include/.  The entry point of each service is renamed with
# -Dmain=<name> so sim_main.c can drive them as threads.

CC      := gcc
CFLAGS  := -Wall -Wextra -O2 -Iinclude -I../qnx8_demo/include
LDFLAGS := -lpthread -lrt

SIM     := rtarch_sim
OBJS    := shim.o sim_main.o \
           sensor_service.o perception_service.o brake_controller.o \
           telemetry_client.o diagnostics_client.o

all: $(SIM)

$(SIM): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LDFLAGS)

shim.o: shim.c include/sys/slog2.h include/sys/neutrino.h include/sys/netmgr.h
	$(CC) $(CFLAGS) -c -o $@ shim.c

sim_main.o: sim_main.c include/sys/neutrino.h
	$(CC) $(CFLAGS) -c -o $@ sim_main.c

sensor_service.o: ../qnx8_demo/sensor_service/main.c ../qnx8_demo/include/rtarch_ipc.h
	$(CC) $(CFLAGS) -Dmain=sensor_service_entry -c -o $@ $<

perception_service.o: ../qnx8_demo/perception_service/main.c ../qnx8_demo/include/rtarch_ipc.h
	$(CC) $(CFLAGS) -Dmain=perception_service_entry -c -o $@ $<

brake_controller.o: ../qnx8_demo/brake_controller/main.c ../qnx8_demo/include/rtarch_ipc.h
	$(CC) $(CFLAGS) -Dmain=brake_controller_entry -c -o $@ $<

telemetry_client.o: ../qnx8_demo/telemetry_client/main.c ../qnx8_demo/include/rtarch_ipc.h
	$(CC) $(CFLAGS) -Dmain=telemetry_client_entry -c -o $@ $<

diagnostics_client.o: ../qnx8_demo/diagnostics_client/main.c ../qnx8_demo/include/rtarch_ipc.h
	$(CC) $(CFLAGS) -Dmain=diagnostics_client_entry -c -o $@ $<

clean:
	rm -f $(OBJS) $(SIM)

.PHONY: all clean
