SHELL = /bin/bash

# common variables
#HOSTNAME = echo hostname
hostname := $(shell hostname)
whoami := $(shell whoami)
CFLAGS = -Wall -Wextra -O2 -ffast-math -funroll-loops# -m32 -DDEBUG
WFLAGS =
OLIBS =
CXX = g++

# DOCUMENTATION
DOXYGEN = /usr/bin/doxygen
DOXYFILE_1 = dpm_src/doxyfile

# EDIT THESE LINES TO INCLUDE GSL
CXLIBS = -lgsl -lgslcblas
XLIBS  = $(CXLIBS)
CXXFLAGS = $(CFLAGS)

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

SRC_4 = b2w_src/b2w.cc
SRC_5 = filter_src/fil.cc
EXE_4 = b2w
EXE_5 = fil
FLAGS_4 = -I./samtools -L./samtools -lbam -lm -lz
FLAGS_5 = -I./samtools -L./samtools -lbam -lm -lz $(XLIBS)
LIB_SAMTOOLS = samtools

SUBDIRS = $(LIB_SAMTOOLS) 

all: $(EXE_1) $(EXE_2) $(EXE_3) $(EXE_4) $(EXE_5)

dpm_src/%.o: dpm_src/%.cpp dpm_src/%.h dpm_src/data_structures.h # only used for C program diri_sampler
	@echo ''
	@echo '*********************************'
	@echo 'building object: $@'
	@echo '*********************************'
	$(CXX) -c $< -o $@ $(CFLAGS) $(WFLAGS)

$(EXE_1): $(OBJS_1) # diri_sampler
	@echo ''
	@echo '*********************************'
	@echo 'building executable: $@'
	@echo '*********************************'
	$(CXX) $(OBJS_1) -o $(EXE_1) -g -O2 $(XLIBS)

$(EXE_2): $(SRC_2) # contain
	@echo ''
	@echo '*********************************'
	@echo 'building executable: $@'
	@echo '*********************************'
	$(CXX) $< -o $(EXE_2) $(FLAGS_2)

$(EXE_3): $(SRC_3) # freqEst
	@echo ''
	@echo '*********************************'
	@echo 'building executable: $@'
	@echo '*********************************'
	$(CXX) $< -o $(EXE_3) $(FLAGS_3)

$(EXE_4): $(SRC_4) $(LIB_SAMTOOLS) # b2w
	@echo ''
	@echo '*********************************'
	@echo 'building executable: $@'
	@echo '*********************************'
	$(CXX) $< -o $(EXE_4) $(CFLAGS) $(FLAGS_4)
	
$(EXE_5): $(SRC_5) # fil
	@echo ''
	@echo '*********************************'
	@echo 'building executable: $@'
	@echo '*********************************'
	$(CXX) $< -o $(EXE_5) $(CFLAGS) $(FLAGS_5)


$(LIB_SAMTOOLS): $(LIB_SAMTOOLS)/Makefile # libbam.a
	@echo ''
	@echo '*********************************'
	@echo 'building libbam.a'
	@echo '*********************************'
	$(MAKE) -C $(LIB_SAMTOOLS) lib


.PHONY : clean doc $(LIB_SAMTOOLS)

clean:
	rm -f $(OBJS_1)
	rm -rf $(EXE_1) $(EXE_1).dSYM
	rm -rf $(EXE_2) $(EXE_2).dSYM
	rm -rf $(EXE_3) $(EXE_3).dSYM
	rm -rf $(EXE_4) $(EXE_4).dSYM
	rm -rf $(EXE_5) $(EXE_5).dSYM
	rm -f *.pyc pythonlib/*.pyc
	for i in $(SUBDIRS); do \
	( cd $$i ; make clean ; cd ../ ) ;\
	done
	rm -f *.bai *.fai

doc:
	$(DOXYGEN) $(DOXYFILE_1)
#	$(DOXYGEN) $(DOXYFILE_2)
