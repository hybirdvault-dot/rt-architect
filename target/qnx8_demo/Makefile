# RTArchitect — QNX 8.0 demo services.
#
#   make            build all six services into bin/
#   make clean      remove build artefacts
#
# The binaries go in bin/ rather than the project root, because each service
# also owns a source directory of the same name (sensor_service/, ...).

include common.mk

SERVICES := sensor_service perception_service brake_controller \
            brake_controller_fixed \
            telemetry_client diagnostics_client

BINDIR := bin
BINS   := $(addprefix $(BINDIR)/,$(SERVICES))
OBJS   := $(SERVICES:%=%/main.o)

all: $(BINS)

$(BINDIR):
	mkdir -p $(BINDIR)

# QNX Neutrino keeps the pthread API inside libc, so there is no -lpthread.
$(BINS): $(BINDIR)/%: %/main.o | $(BINDIR)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

$(OBJS): %/main.o: %/main.c include/rtarch_ipc.h
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(OBJS)
	rm -rf $(BINDIR)

.PHONY: all clean
