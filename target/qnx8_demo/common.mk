# Shared QNX 8.0 build configuration.
#
# Point QNX_HOST at your QNX SDP installation.  The default matches a
# standard QNX 8.0 SDP install on a Linux host.

QNX_HOST ?= /opt/qnx800/host/linux/x86_64
CC        := $(QNX_HOST)/usr/bin/qcc
CFLAGS    := -Wall -Wextra -O2 -Iinclude
LDFLAGS   := -lslog2

%.o: %.c include/rtarch_ipc.h
	$(CC) $(CFLAGS) -c -o $@ $<
