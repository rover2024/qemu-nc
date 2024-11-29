LIBNAME := @LIBRARY_NAME@

CC := gcc

INCLUDE_DIRS := \
	/home/overworld/Documents/ccxxprojs/qemu-nc/include

LINK_DIRS := \
	/home/overworld/Documents/ccxxprojs/qemu-nc/build/Release/lib

DEFINITIONS := \
	X64NC_LIBRARY_NAME=\"$(LIBNAME)\"

CCFLAGS := -O2 -fPIC \
	-fno-stack-protector -fno-exceptions \
	$(foreach item,$(INCLUDE_DIRS),-I$(item)) \
	$(foreach item,$(LINK_DIRS),-L$(item)) \
	$(foreach item,$(DEFINITIONS),-D$(item))

all: lib$(LIBNAME).so lib$(LIBNAME)_host_bridge.so

lib$(LIBNAME)_host_bridge.so: x64nc_delegate_host.c
	$(CC) -o $@ $(CCFLAGS) $< -shared -Wl,-z,defs -ldl

lib$(LIBNAME).so: x64nc_delegate_guest.c
	$(CC) -o $@ $(CCFLAGS) $< -shared -Wl,-z,defs -lx64nc-guestrt

clean:
	rm lib$(LIBNAME).so lib$(LIBNAME)_host_bridge.so