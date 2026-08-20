CC      := gcc
SRC     := src
TESTS   := tests
BUILD   := build

OPT     := -O3 -flto -march=native -mtune=native -funroll-loops \
           -fomit-frame-pointer -fstrict-aliasing -fno-plt
WARN    := -Wall -Wextra -Wpedantic -Werror -Wconversion -Wsign-conversion \
           -Wshadow -Wundef -Wformat=2 -Wformat-security -Wformat-nonliteral \
           -Wcast-qual -Wcast-align -Wwrite-strings -Wstrict-prototypes \
           -Wmissing-prototypes -Wpointer-arith -Wswitch-enum \
           -Wduplicated-cond -Wduplicated-branches -Wlogical-op \
           -Wnull-dereference -Wstack-usage=16384
CFLAGS  := -std=gnu11 -pthread $(OPT) $(WARN) -I$(SRC) \
           -Wno-objc-root-class
LDFLAGS := -flto -pthread -lobjc

ENGINE := $(BUILD)/BBRootObject.o $(BUILD)/BBCore.o $(BUILD)/BBEval.o \
          $(BUILD)/BBSearch.o $(BUILD)/BBUCI.o

.PHONY: all test perft unit lint clean

all: $(BUILD)/chess-objc $(BUILD)/perft $(BUILD)/unit

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: $(SRC)/%.m | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/%.o: $(TESTS)/%.m | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/chess-objc: $(ENGINE) $(BUILD)/main.o
	$(CC) $(LDFLAGS) $^ -o $@

$(BUILD)/perft: $(ENGINE) $(BUILD)/perft_main.o
	$(CC) $(LDFLAGS) $^ -o $@

$(BUILD)/unit: $(ENGINE) $(BUILD)/unit_main.o
	$(CC) $(LDFLAGS) $^ -o $@

perft: $(BUILD)/perft
	$(BUILD)/perft

unit: $(BUILD)/unit
	$(BUILD)/unit

test: unit perft

lint: SHELL := /bin/sh
lint: $(SRC)/*.m $(SRC)/*.h $(TESTS)/*.m
	./lint.sh

clean:
	rm -rf $(BUILD)