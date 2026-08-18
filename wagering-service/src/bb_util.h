#ifndef BB_UTIL_H
#define BB_UTIL_H

#include <stddef.h>
#include <stdint.h>

/*
 * bb_util: small shared helpers for the wagering-service.
 * Hex codecs, the splitmix64 mixer, and a growable byte buffer.
 */

/* splitmix64: deterministic 64-bit mixer (public domain / widely published). */
uint64_t bb_splitmix64(uint64_t x);

/* Double-ended rotate helpers. */
uint32_t bb_rotl32(uint32_t v, int n);
uint32_t bb_rotr32(uint32_t v, int n);
uint64_t bb_rotl64(uint64_t v, int n);

/* Hex: encode `src_len` bytes into `dst` (needs 2*src_len+1), decode back. */
void bb_hex_encode(const uint8_t *src, size_t src_len, char *dst);
int bb_hex_decode(const char *src, size_t src_len, uint8_t *dst); /* returns length or -1 */

/* Growable byte buffer used by the JSON writer. */
typedef struct {
    uint8_t *data;
    size_t len;
    size_t cap;
} bb_buf;

void bb_buf_init(bb_buf *b);
void bb_buf_free(bb_buf *b);
void bb_buf_push(bb_buf *b, const void *bytes, size_t n);
void bb_buf_push_c(bb_buf *b, char c);
void bb_buf_push_str(bb_buf *b, const char *s);
void bb_buf_reset(bb_buf *b);

#endif /* BB_UTIL_H */