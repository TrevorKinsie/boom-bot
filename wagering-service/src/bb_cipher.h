#ifndef BB_CIPHER_H
#define BB_CIPHER_H

#include <stddef.h>
#include <stdint.h>

/*
 * bb-cipher: the wagering service's own encryption.
 *
 * BB64 is a hand-rolled ARX block cipher: 64-bit blocks, 128-bit keys,
 * 27 rounds of a Speck-style add/rotate/xor round function with a key
 * schedule derived from the splitmix64 mixer. No external crypto library
 * is linked anywhere in the service; every primitive lives in this file.
 *
 * Honestly documented: this is a from-scratch construction. It is the
 * cipher the service uses for its at-rest envelope (see bb_store.h), it is
 * deterministic and regression-checked with fixed known-answer vectors, but
 * it has NOT been cryptanalysed and must not be treated as protecting real
 * currency or secrets of material value.
 */

#define BB64_BLOCK 8
#define BB64_KEY 16
#define BB64_ROUNDS 27
#define BB64_TAG 8

typedef struct {
    uint32_t rk[BB64_ROUNDS];
} bb64_ctx;

/* Expand a 128-bit key into the round-key schedule. */
void bb64_key(bb64_ctx *ctx, const uint8_t key[BB64_KEY]);

/* Encrypt / decrypt one 64-bit block in place. */
void bb64_encrypt(const bb64_ctx *ctx, uint8_t block[BB64_BLOCK]);
void bb64_decrypt(const bb64_ctx *ctx, uint8_t block[BB64_BLOCK]);

/* CTR mode: in-place XOR stream transformation over arbitrary lengths.
   The 8-byte nonce selects the starting counter block. */
void bb64_ctr_crypt(const bb64_ctx *ctx, const uint8_t nonce[BB64_BLOCK],
                    uint8_t *data, size_t len);

/* CBC-MAC over a whole-block data buffer (len % 8 == 0); 64-bit tag. */
void bb64_cbc_mac(const bb64_ctx *ctx, const uint8_t *data, size_t len,
                  uint8_t tag[BB64_TAG]);

/* Known-answer self-test; returns 1 when the cipher behaves as pinned. */
int bb64_selfcheck(void);

#endif /* BB_CIPHER_H */