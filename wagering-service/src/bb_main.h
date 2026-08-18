#ifndef BB_MAIN_H
#define BB_MAIN_H

#include "bb_store.h"
#include "bb_wallet.h"

/*
 * Protocol entry point shared by main() and the test harness.
 * handle_line processes one JSON-lines request and writes the response
 * into out (NUL-terminated). Returns 0 on success, -1 on protocol errors
 * the caller should ignore (out is still written).
 */

#define BB_PROTO_OUT_SIZE (64u * 1024u)

int bb_handle_line(const char *line, char *out, size_t out_size, bb_store *svc);

#endif /* BB_MAIN_H */