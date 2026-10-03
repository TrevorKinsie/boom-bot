#include "bb_cipher.h"

#include <string.h>

#include "bb_util.h"

static uint32_t load32_le(const uint8_t *p) {
    return (uint32_t) p[0] | ((uint32_t) p[1] << 8) | ((uint32_t) p[2] << 16) |
           ((uint32_t) p[3] << 24);
}

static void store32_le(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t) v;
    p[1] = (uint8_t) (v >> 8);
    p[2] = (uint8_t) (v >> 16);
    p[3] = (uint8_t) (v >> 24);
}

/*
 * Round function: Speck-style ARX mixing over two 32-bit words.
 *   enc: x = rotr(x,8); x += y; y = rotl(y,3); y ^= x; x ^= key
 */
static void bb64_round(uint32_t *x, uint32_t *y, uint32_t k) {
    *x = bb_rotr32(*x, 8);
    *x += *y;
    *y = bb_rotl32(*y, 3);
    *y ^= *x;
    *x ^= k;
}

static void bb64_unround(uint32_t *x, uint32_t *y, uint32_t k) {
    *x ^= k;
    *y ^= *x;
    *y = bb_rotr32(*y, 3);
    *x -= *y;
    *x = bb_rotl32(*x, 8);
}

void bb64_key(bb64_ctx *ctx, const uint8_t key[BB64_KEY]) {
    uint32_t words[4];
    for (int i = 0; i < 4; i++) {
        words[i] = load32_le(key + 4 * i);
    }
    uint64_t mixer = (uint64_t) words[0] | ((uint64_t) words[1] << 32);
    for (int i = 0; i < BB64_ROUNDS; i++) {
        mixer = bb_splitmix64(mixer ^ (uint64_t) i * 0x9E3779B97F4A7C15ULL ^ words[i % 4]);
        ctx->rk[i] = (uint32_t) (mixer >> 32);
    }
}

void bb64_encrypt(const bb64_ctx *ctx, uint8_t block[BB64_BLOCK]) {
    uint32_t x = load32_le(block);
    uint32_t y = load32_le(block + 4);
    for (int i = 0; i < BB64_ROUNDS; i++) {
        bb64_round(&x, &y, ctx->rk[i]);
    }
    store32_le(block, x);
    store32_le(block + 4, y);
}

void bb64_decrypt(const bb64_ctx *ctx, uint8_t block[BB64_BLOCK]) {
    uint32_t x = load32_le(block);
    uint32_t y = load32_le(block + 4);
    for (int i = BB64_ROUNDS - 1; i >= 0; i--) {
        bb64_unround(&x, &y, ctx->rk[i]);
    }
    store32_le(block, x);
    store32_le(block + 4, y);
}

void bb64_ctr_crypt(const bb64_ctx *ctx, const uint8_t nonce[BB64_BLOCK],
                    uint8_t *data, size_t len) {
    uint64_t nonce64 = 0;
    for (int i = 0; i < 8; i++) {
        nonce64 |= (uint64_t) nonce[i] << (8 * i);
    }
    uint64_t counter = nonce64;
    uint8_t stream[BB64_BLOCK];
    while (len > 0) {
        for (int i = 0; i < 8; i++) {
            stream[i] = (uint8_t) (counter >> (8 * i));
        }
        bb64_encrypt(ctx, stream);
        size_t chunk = len < BB64_BLOCK ? len : BB64_BLOCK;
        for (size_t i = 0; i < chunk; i++) {
            data[i] ^= stream[i];
        }
        data += chunk;
        len -= chunk;
        counter += 1;
        if (counter == 0) {
            counter = nonce64; /* wrap: cycle the stream, never the key */
        }
    }
}

void bb64_cbc_mac(const bb64_ctx *ctx, const uint8_t *data, size_t len,
                  uint8_t tag[BB64_TAG]) {
    uint8_t block[BB64_BLOCK] = {0};
    size_t off = 0;
    while (off < len) {
        size_t chunk = len - off < BB64_BLOCK ? len - off : BB64_BLOCK;
        for (size_t i = 0; i < chunk; i++) {
            block[i] ^= data[off + i];
        }
        bb64_encrypt(ctx, block);
        off += chunk;
    }
    memcpy(tag, block, BB64_TAG);
}

/* Known-answer vectors: subkeys, one block, one CTR stream, one MAC. */
int bb64_selfcheck(void) {
    const uint8_t key[BB64_KEY] = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
                                   0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f};
    const uint8_t plain[BB64_BLOCK] = {0x6b, 0xc1, 0xbe, 0xe2, 0x2e, 0x40, 0x9f, 0x96};

    bb64_ctx ctx;
    bb64_key(&ctx, key);
    if (ctx.rk[0] != 0x52E2FFAFU || ctx.rk[BB64_ROUNDS - 1] != 0x910E984DU) {
        return 0;
    }

    uint8_t block[BB64_BLOCK];
    memcpy(block, plain, BB64_BLOCK);
    bb64_encrypt(&ctx, block);
    const uint8_t expected[BB64_BLOCK] = {0xe4, 0x44, 0x29, 0x0f, 0xe0, 0x21, 0xef, 0x1b};
    if (memcmp(block, expected, BB64_BLOCK) != 0) {
        return 0;
    }
    bb64_decrypt(&ctx, block);
    if (memcmp(block, plain, BB64_BLOCK) != 0) {
        return 0;
    }

    uint8_t data[16] = {0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
                        0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff};
    uint8_t copy[16];
    memcpy(copy, data, 16);
    const uint8_t nonce[8] = {0xde, 0xad, 0xbe, 0xef, 0x00, 0x00, 0x00, 0x01};
    bb64_ctr_crypt(&ctx, nonce, copy, 16);
    const uint8_t expected_ctr[16] = {0x16, 0xf3, 0x60, 0xeb, 0xcb, 0xb5, 0x7f, 0xa5,
                                      0xaa, 0x47, 0xeb, 0xd5, 0x0c, 0x25, 0x90, 0x78};
    if (memcmp(copy, expected_ctr, 16) != 0) {
        return 0;
    }
    bb64_ctr_crypt(&ctx, nonce, copy, 16);
    if (memcmp(copy, data, 16) != 0) {
        return 0;
    }

    uint8_t tag[BB64_TAG];
    bb64_cbc_mac(&ctx, data, 16, tag);
    const uint8_t expected_tag[BB64_TAG] = {0x5e, 0xf5, 0x3e, 0x52, 0x94, 0xae, 0xb8, 0x56};
    if (memcmp(tag, expected_tag, BB64_TAG) != 0) {
        return 0;
    }
    return 1;
}