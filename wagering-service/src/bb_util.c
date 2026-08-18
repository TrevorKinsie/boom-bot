#include "bb_util.h"

#include <stdlib.h>
#include <string.h>

uint64_t bb_splitmix64(uint64_t x) {
    x += 0x9E3779B97F4A7C15ULL;
    uint64_t z = x;
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

uint32_t bb_rotl32(uint32_t v, int n) {
    return (v << n) | (v >> (32 - n));
}

uint32_t bb_rotr32(uint32_t v, int n) {
    return (v >> n) | (v << (32 - n));
}

uint64_t bb_rotl64(uint64_t v, int n) {
    return (v << n) | (v >> (64 - n));
}

static const char HEX_DIGITS[] = "0123456789abcdef";

void bb_hex_encode(const uint8_t *src, size_t src_len, char *dst) {
    for (size_t i = 0; i < src_len; i++) {
        dst[i * 2] = HEX_DIGITS[src[i] >> 4];
        dst[i * 2 + 1] = HEX_DIGITS[src[i] & 0x0f];
    }
    dst[src_len * 2] = '\0';
}

static int hex_val(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int bb_hex_decode(const char *src, size_t src_len, uint8_t *dst) {
    if (src_len % 2 != 0) return -1;
    for (size_t i = 0; i < src_len / 2; i++) {
        int hi = hex_val(src[i * 2]);
        int lo = hex_val(src[i * 2 + 1]);
        if (hi < 0 || lo < 0) return -1;
        dst[i] = (uint8_t) ((hi << 4) | lo);
    }
    return (int) (src_len / 2);
}

void bb_buf_init(bb_buf *b) {
    b->data = NULL;
    b->len = 0;
    b->cap = 0;
}

void bb_buf_free(bb_buf *b) {
    free(b->data);
    b->data = NULL;
    b->len = 0;
    b->cap = 0;
}

void bb_buf_reset(bb_buf *b) {
    b->len = 0;
}

static void bb_buf_grow(bb_buf *b, size_t need) {
    if (b->len + need <= b->cap) return;
    size_t cap = b->cap ? b->cap : 256;
    while (cap < b->len + need) cap *= 2;
    b->data = (uint8_t *) realloc(b->data, cap);
    b->cap = cap;
}

void bb_buf_push(bb_buf *b, const void *bytes, size_t n) {
    bb_buf_grow(b, n);
    memcpy(b->data + b->len, bytes, n);
    b->len += n;
}

void bb_buf_push_c(bb_buf *b, char c) {
    bb_buf_grow(b, 1);
    b->data[b->len++] = (uint8_t) c;
}

void bb_buf_push_str(bb_buf *b, const char *s) {
    bb_buf_push(b, s, strlen(s));
}