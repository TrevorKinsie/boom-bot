#ifndef BB_STORE_H
#define BB_STORE_H

#include <stddef.h>
#include <stdint.h>

#include "bb_cipher.h"
#include "bb_wallet.h"

/*
 * bb_store: the wagering service's encrypted at-rest store.
 *
 * Each wallet persists as two files in the data directory:
 *   u<16 hex chars of the user id>.wlog   append-only event log
 *   u<...>.snap                            latest snapshot
 *
 * Every record is sealed with the service's own cipher before hitting disk:
 *   record = nonce(8) || CTR-encrypted(payload) || CBC-MAC tag(8)
 * with the tag computed over (nonce || ciphertext) under a second key
 * (encrypt-then-MAC), so a tampered or truncated log fails the tag check
 * and refuses to load -- the store never mixes ciphertext it cannot
 * authenticate. Event log records add a 4-byte little-endian length header
 * for framing; snapshot files prepend a 4-byte magic "BBSN".
 *
 * The process is single-threaded and owns the files exclusively; no locking
 * is performed.
 */

#define BB_STORE_MAGIC 0x4242534eu /* "BBSN" BE */
#define BB_STORE_LOG_HEADER 8      /* nonce */
#define BB_STORE_TAG BB64_TAG
#define BB_STORE_OVERHEAD (BB_STORE_LOG_HEADER + BB_STORE_TAG)
#define BB_STORE_MAX_RECORD (1u << 20) /* 1 MiB sanity ceiling */

typedef struct {
    bb64_ctx enc;
    bb64_ctx mac;
    char dir[512];
    int use_fsync;
    char err[256];
} bb_store;

/* Configure the store. key_enc/key_mac are the two 128-bit halves of the
   master key; data_dir is where the per-wallet files live. */
void bb_store_init(bb_store *s, const uint8_t key_enc[16], const uint8_t key_mac[16],
                   const char *data_dir, int use_fsync);

/* Load a wallet from disk: snapshot (if any) + replayed events. Returns:
   1 loaded, 0 not found (fresh wallet, w untouched), -1 corrupt (s->err set). */
int bb_store_load(bb_store *s, const char *user, bb_wallet *w);

/* Append one event to the wallet's log and flush. Returns 0 on I/O failure. */
int bb_store_append(bb_store *s, const char *user, const bb_event *ev);

/* Overwrite the wallet snapshot (called periodically / on close). */
int bb_store_snapshot(bb_store *s, const char *user, const bb_wallet *w);

/* Opaque file path for a wallet's store file (exposed for tests/ops). */
void bb_store_file_path(bb_store *s, const char *user, const char *suffix,
                        char *path, size_t path_size);

/* Delete a wallet's files (used by tests). */
void bb_store_discard(bb_store *s, const char *user);

#endif /* BB_STORE_H */