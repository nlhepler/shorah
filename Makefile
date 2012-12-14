SHELL = /bin/bash

# common variables
#HOSTNAME = echo hostname
hostname := $(shell hostname)
whoami := $(shell whoami)
host-type := $(shell uname)
CCFLAGS = -Wall -Wextra -O2 -ffast-math -funroll-loops# -m32 -DDEBUG
WFLAGS =
OLIBS = 
CPP = g++
SUBDIRS = samtools

# DOCUMENTATION
DOXYGEN = /usr/bin/doxygen
DOXYFILE_1 = dpm_src/doxyfile

# EDIT THESE LINES TO INCLUDE GSL
CXLIBS = -lgsl -lgslcblas
CFLAGS = $(CCFLAGS) -I/usr/local/include
XLIBS  = -L/usr/local/lib $(CXLIBS)
CPPFLAGS = $(CFLAGS)

#SRC_1 = dpm_src/dmm_sampler.cpp
OBJS_1 = dpm_src/dpm_sampler.o
EXE_1 = diri_sampler

SRC_2 = contain_src/contain.cc
EXE_2 = contain
FLAGS_2 = -g -O3# -Wall

#OBJS_3 = freqEst_src/freqEst.o
SRC_3 = freqEst_src/freqEst.cc
EXE_3 = freqEst
FLAGS_3 = -g -O3 -Wall -ffast-math

SRC_4 = b2w_src/b2w.c
SRC_5 = filter_src/fil.c
EXE_4 = b2w
EXE_5 = fil
FLAGS_4 = -Isamtools -Lsamtools -lbam -lm -lz
FLAGS_5 = -Isamtools -Lsamtools -lbam -lm -lz $(XLIBS) 
LIB_SAMTOOLS = samtools


%.o : %.cpp %.h data_structures.h Makefile # only used for C program diri_sampler
	@echo ''
	@echo '*********************************'
	@echo '   making object: $@ '
	@echo '*********************************'
	$(CPP) $(CFLAGS) $(WFLAGS) $(XLIBS) -c $< -o $@

all: $(EXE_1) $(EXE_2) $(EXE_3) $(LIB_SAMTOOLS) $(EXE_4) $(EXE_5)

$(EXE_1): $(OBJS_1) Makefile #diri_sampler
	@echo ''
	@echo '*********************************'
	@echo ' making executable: $@ '
	@echo '*********************************'
	$(CPP) $(XLIBS) $(OBJS_1) -g -O2 -o  $(EXE_1)

	@echo '*******************'
	@echo 'compiled for $(host-type)'

$(EXE_2): $(SRC_2) Makefile #contain
	@echo ''
	@echo '*********************************'
	@echo ' making executable: $@ '
	@echo '*********************************'
	$(CPP) $(FLAGS_2) $(SRC_2) -o $(EXE_2)

	@echo '*******************'
	@echo 'compiled for $(host-type)'

$(EXE_3): $(SRC_3) Makefile #freqEst
	@echo ''
	@echo '*********************************'
	@echo ' making executable: $@ '
	@echo '*********************************'
	$(CPP) $(FLAGS_3) $(SRC_3) -o $(EXE_3)

	@echo '*******************'
	@echo 'compiled for $(host-type)'

$(EXE_4): $(SRC_4) Makefile samtools #b2w
	@echo ''
	@echo '*********************************'
	@echo ' making executable: $@ '
	@echo '*********************************'
	$(CPP) $(SRC_4) $(CFLAGS) $(FLAGS_4) -o $(EXE_4)
	
$(EXE_5): $(SRC_5) Makefile #fil
	@echo ''
	@echo '*********************************'
	@echo ' making executable: $@ '
	@echo '*********************************'
	$(CPP) $(SRC_5) $(CFLAGS) $(FLAGS_5) -o $(EXE_5)


$(LIB_SAMTOOLS): Makefile
	@echo ''
	@echo '*********************************'
	@echo 'Building samtools'
	@echo '*********************************'
	for i in $(SUBDIRS) ; do \
	( cd $$i ; make ; cd ../ ) ; \
	done


.PHONY : clean doc

clean:
	rm -rf $(OBJS_1)
	rm -rf $(EXE_1) $(EXE_1).dSYM
	rm -rf $(EXE_2) $(EXE_2).dSYM
	rm -rf $(EXE_3) $(EXE_3).dSYM
	rm -rf $(EXE_4) $(EXE_4).dSYM
	rm -rf $(EXE_5) $(EXE_5).dSYM
	rm -rf *.pyc pythonlib/*.pyc
	for i in $(SUBDIRS); do \
	( cd $$i ; make clean ; cd ../ ) ;\
	done
doc:
	$(DOXYGEN) $(DOXYFILE_1)
#	$(DOXYGEN) $(DOXYFILE_2)
