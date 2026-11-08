# RTArchitect — QNX 8.0 demo services.
#
#   make            build all five services
#   make clean      remove build artefacts
#
# The binaries land in target/qnx8_demo/ and are copied into the QNX QEMU
# guest (or run natively on the target).

include common.mk

SERVICES := sensor_service perception_service brake_controller \
            telemetry_client diagnostics_client

BINS := $(SERVICES)
OBJS := $(SERVICES:%=%/main.o)

all: $(BINS)

$(BINS): %: %/main.o
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(OBJS) $(BINS)

.PHONY: all clean
