/*
 * Self-tests for the wagering service. Built as a standalone binary by
 * build.sh; runs the full battery and exits non-zero on any failure.
 *
 *   cipher KAT vectors + round trips + tamper sensitivity
 *   money parsing/formatting/overflow
 *   wallet fold invariants + sponsorship records
 *   encrypted store round-trip, snapshot replay, tamper detection
 *   JSON-lines protocol through bb_handle_line
 */
#define BB_TEST 1

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include "bb_cipher.h"
#include "bb_main.h"
#include "bb_money.h"
#include "bb_store.h"
#include "bb_util.h"
#include "bb_wallet.h"

static int failures = 0;

#define CHECK(cond)                                                           \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);   \
            failures++;                                                       \
        }                                                                     \
    } while (0)

static void test_cipher(void) {
    CHECK(bb64_selfcheck());

    uint8_t key[16];
    memset(key, 0xAB, 16);
    bb64_ctx ctx;
    bb64_key(&ctx, key);

    uint8_t block[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    uint8_t original[8];
    memcpy(original, block, 8);
    bb64_encrypt(&ctx, block);
    CHECK(memcmp(block, original, 8) != 0);
    bb64_decrypt(&ctx, block);
    CHECK(memcmp(block, original, 8) == 0);

    /* different key -> different ciphertext */
    uint8_t key2[16];
    memset(key2, 0xCD, 16);
    bb64_ctx ctx2;
    bb64_key(&ctx2, key2);
    uint8_t block2[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    bb64_encrypt(&ctx2, block2);
    bb64_encrypt(&ctx, block);
    CHECK(memcmp(block, block2, 8) != 0);

    /* CTR: deterministic stream, inverse under the same nonce */
    uint8_t data[17];
    for (int i = 0; i < 17; i++) data[i] = (uint8_t) i;
    uint8_t nonce[8] = {0, 0, 0, 0, 0, 0, 0, 9};
    uint8_t copy[17];
    memcpy(copy, data, 17);
    bb64_ctr_crypt(&ctx, nonce, copy, 17);
    CHECK(memcmp(copy, data, 17) != 0);
    bb64_ctr_crypt(&ctx, nonce, copy, 17);
    CHECK(memcmp(copy, data, 17) == 0);

    /* CBC-MAC: one flipped bit changes the tag */
    uint8_t tag1[8], tag2[8];
    bb64_cbc_mac(&ctx, data, 16, tag1);
    data[3] ^= 1;
    bb64_cbc_mac(&ctx, data, 16, tag2);
    CHECK(memcmp(tag1, tag2, 8) != 0);
    data[3] ^= 1;
}

static void test_money(void) {
    bb_money m;
    CHECK(bb_money_parse("10", &m) && m == 1000);
    CHECK(bb_money_parse("10.5", &m) && m == 1050);
    CHECK(bb_money_parse("10.50", &m) && m == 1050);
    CHECK(bb_money_parse("0.01", &m) && m == 1);
    CHECK(bb_money_parse("0", &m) && m == 0);
    CHECK(bb_money_parse("-1.25", &m) && m == -125);
    CHECK(!bb_money_parse("10.505", &m));   /* quantisation */
    CHECK(!bb_money_parse("", &m));
    CHECK(!bb_money_parse("abc", &m));
    CHECK(!bb_money_parse("1..2", &m));

    char buf[32];
    bb_money_fmt(1050, buf);
    CHECK(strcmp(buf, "10.50") == 0);
    bb_money_fmt(-125, buf);
    CHECK(strcmp(buf, "-1.25") == 0);
    bb_money_fmt(0, buf);
    CHECK(strcmp(buf, "0.00") == 0);

    bb_money out;
    CHECK(bb_money_add(1000, 500, &out) && out == 1500);
    CHECK(bb_money_sub(1000, 500, &out) && out == 500);
    CHECK(!bb_money_sub(100, 101, &out));   /* negative money not representable */
    CHECK(bb_money_scale(1000, 3, &out) && out == 3000);
    CHECK(!bb_money_scale(BB_MONEY_MAX, 2, &out));
}

static void test_wallet(void) {
    bb_wallet w;
    bb_event ev;

    bb_wallet_init(&w);
    CHECK(bb_wallet_cmd_provision(&w, 10000, &ev));
    CHECK(w.exists && w.balance == 10000 && w.seq == 1);

    CHECK(bb_wallet_cmd_debit(&w, 1500, "roulette_bet", &ev));
    CHECK(w.balance == 8500);
    CHECK(!bb_wallet_cmd_debit(&w, 9000, "overdraw", &ev)); /* insufficient funds */
    CHECK(w.balance == 8500 && strstr(w.err, "insufficient") != NULL);

    CHECK(bb_wallet_cmd_credit(&w, 2000, "payout", &ev));
    CHECK(w.balance == 10500);

    CHECK(bb_wallet_cmd_wager(&w, 500, 3500, "roulette", &ev));
    CHECK(w.total_wagered == 500 && w.total_won == 3500 && w.biggest_win == 3500);
    CHECK(w.games_played == 1);

    CHECK(bb_wallet_cmd_award_spins(&w, 3, &ev));
    CHECK(w.free_spins == 3);
    CHECK(bb_wallet_cmd_redeem_spin(&w, &ev));
    CHECK(w.free_spins == 2);
    CHECK(bb_wallet_cmd_redeem_spin(&w, &ev));
    CHECK(bb_wallet_cmd_redeem_spin(&w, &ev));
    CHECK(!bb_wallet_cmd_redeem_spin(&w, &ev)); /* no free spins left */
    CHECK(strstr(w.err, "no free spins") != NULL);

    CHECK(bb_wallet_cmd_reset(&w, 5000, &ev));
    CHECK(w.balance == 5000);

    /* sponsorship */
    CHECK(bb_wallet_cmd_sponsor(&w, 7500, "Acme Casino", "welcome", "SP-001", &ev));
    CHECK(w.balance == 12500 && w.sponsorship_count == 1);
    CHECK(strcmp(w.sponsorships[0].ref, "SP-001") == 0);
    CHECK(w.sponsorships[0].amount == 7500);
    CHECK(strcmp(w.sponsorships[0].sponsor, "Acme Casino") == 0);
    CHECK(strcmp(w.sponsorships[0].purpose, "welcome") == 0);
    CHECK(!bb_wallet_cmd_sponsor(&w, 0, "Acme", "zero", "SP-002", &ev)); /* must be positive */
    CHECK(w.sponsorship_count == 1);

    /* snapshot round-trip */
    bb_jval *snap = bb_wallet_to_json(&w);
    char *snap_str = bb_json_to_string(snap);
    bb_wallet w2;
    bb_jval *dom = bb_json_parse(snap_str);
    CHECK(dom != NULL && bb_wallet_from_json(dom, &w2));
    CHECK(w2.balance == w.balance && w2.seq == w.seq && w2.free_spins == 0);
    CHECK(w2.sponsorship_count == w.sponsorship_count);
    CHECK(strcmp(w2.sponsorships[0].ref, "SP-001") == 0);
    bb_json_free(dom);
    free(snap_str);
    bb_json_free(snap);
    bb_wallet_free(&w2);
    bb_wallet_free(&w);

    /* event codec round-trip */
    bb_event ev2;
    bb_jval *jev = bb_event_to_json(&ev);
    char *ev_str = bb_json_to_string(jev);
    bb_jval *dom2 = bb_json_parse(ev_str);
    CHECK(dom2 != NULL && bb_event_from_json(dom2, &ev2));
    CHECK(ev2.type == ev.type && ev2.seq == ev.seq && ev2.amount == ev.amount);
    CHECK(strcmp(ev2.sponsor, ev.sponsor) == 0 && strcmp(ev2.ref, ev.ref) == 0);
    bb_json_free(dom2);
    free(ev_str);
    bb_json_free(jev);
}

static void test_store(void) {
    char dir[] = "/tmp/bb_wagering_test_data";
    system("rm -rf /tmp/bb_wagering_test_data");
    mkdir(dir, 0700);

    uint8_t key[32];
    memset(key, 0x5A, 32);
    bb_store s;
    bb_store_init(&s, key, key + 16, dir, 0);

    bb_wallet w;
    int rc = bb_store_load(&s, "alice", &w);
    CHECK(rc == 0); /* fresh wallet */

    bb_event ev;
    CHECK(bb_wallet_cmd_provision(&w, 10000, &ev));
    CHECK(bb_store_append(&s, "alice", &ev));
    CHECK(bb_wallet_cmd_credit(&w, 500, "welcome_bonus", &ev));
    CHECK(bb_store_append(&s, "alice", &ev));
    CHECK(bb_wallet_cmd_sponsor(&w, 2500, "SponsorCo", "launch", "SP-X", &ev));
    CHECK(bb_store_append(&s, "alice", &ev));
    CHECK(bb_store_snapshot(&s, "alice", &w));
    CHECK(bb_wallet_cmd_debit(&w, 1000, "roulette", &ev));
    CHECK(bb_store_append(&s, "alice", &ev));

    /* fresh wallet object: snapshot + replay must reconstruct exactly
       (balance 13000 at snapshot time, then the 1000 debit replays) */
    bb_wallet w2;
    rc = bb_store_load(&s, "alice", &w2);
    CHECK(rc == 1);
    CHECK(w2.exists && w2.balance == w.balance);
    CHECK(w2.seq == w.seq && w2.sponsorship_count == w.sponsorship_count);
    CHECK(strcmp(w2.sponsorships[0].ref, "SP-X") == 0);
    CHECK(w2.balance == 12000);

    /* tampering with the log must be detected */
    char path[600];
    bb_store_file_path(&s, "alice", "wlog", path, sizeof(path));
    FILE *f = fopen(path, "r+b");
    CHECK(f != NULL);
    fseek(f, 20, SEEK_SET);
    long pos = ftell(f);
    uint8_t byte;
    fread(&byte, 1, 1, f);
    byte ^= 0x40;
    fseek(f, pos, SEEK_SET);
    fwrite(&byte, 1, 1, f);
    fclose(f);

    bb_wallet w3;
    rc = bb_store_load(&s, "alice", &w3);
    CHECK(rc == -1);
    CHECK(strstr(s.err, "authentication") != NULL);

    bb_wallet_free(&w);
    bb_wallet_free(&w2);
    bb_store_discard(&s, "alice");
}

static void test_protocol(void) {
    char dir[] = "/tmp/bb_wagering_proto_data";
    system("rm -rf /tmp/bb_wagering_proto_data");
    mkdir(dir, 0700);

    uint8_t key[32];
    memset(key, 0x77, 32);
    bb_store s;
    bb_store_init(&s, key, key + 16, dir, 0);

    char out[BB_PROTO_OUT_SIZE];

    bb_handle_line("{\"id\":\"x\",\"op\":\"wallet_provision\",\"user\":\"bob\","
                   "\"starting_balance\":\"50\"}", out, sizeof(out), &s);
    CHECK(strstr(out, "\"ok\":true") != NULL && strstr(out, "\"balance\":\"50.00\"") != NULL);

    bb_handle_line("{\"id\":\"x\",\"op\":\"wallet_debit\",\"user\":\"bob\","
                   "\"amount\":\"10\",\"reason\":\"bet\"}", out, sizeof(out), &s);
    CHECK(strstr(out, "\"balance\":\"40.00\"") != NULL);

    bb_handle_line("{\"id\":\"x\",\"op\":\"wallet_debit\",\"user\":\"bob\","
                   "\"amount\":\"99\",\"reason\":\"bet\"}", out, sizeof(out), &s);
    CHECK(strstr(out, "\"insufficient_funds\"") != NULL);

    bb_handle_line("{\"id\":\"x\",\"op\":\"sponsor_start\",\"user\":\"bob\","
                   "\"sponsor\":\"MegaCorp\",\"amount\":\"25\",\"purpose\":\"seasonal\",\"ref\":\"M-1\"}",
                   out, sizeof(out), &s);
    CHECK(strstr(out, "\"ok\":true") != NULL && strstr(out, "\"balance\":\"65.00\"") != NULL);

    bb_handle_line("{\"id\":\"x\",\"op\":\"sponsorships_list\",\"user\":\"bob\"}",
                   out, sizeof(out), &s);
    CHECK(strstr(out, "MegaCorp") != NULL && strstr(out, "M-1") != NULL);

    /* replay in a fresh service instance: encrypted at-rest state survives */
    bb_store s2;
    bb_store_init(&s2, key, key + 16, dir, 0);
    bb_handle_line("{\"id\":\"x\",\"op\":\"wallet_get\",\"user\":\"bob\"}",
                   out, sizeof(out), &s2);
    CHECK(strstr(out, "\"balance\":\"65.00\"") != NULL);

    /* unknown user */
    bb_handle_line("{\"id\":\"x\",\"op\":\"wallet_get\",\"user\":\"carol\"}",
                   out, sizeof(out), &s2);
    CHECK(strstr(out, "\"no_wallet\"") != NULL);

    /* malformed input */
    bb_handle_line("not json at all", out, sizeof(out), &s2);
    CHECK(strstr(out, "\"parse_error\"") != NULL);

    /* crypto selfcheck */
    bb_handle_line("{\"id\":\"x\",\"op\":\"crypto_selfcheck\"}", out, sizeof(out), &s2);
    CHECK(strstr(out, "\"kat\":\"ok\"") != NULL);

    system("rm -rf /tmp/bb_wagering_proto_data");
}

int main(void) {
    test_cipher();
    test_money();
    test_wallet();
    test_store();
    test_protocol();

    if (failures == 0) {
        printf("wagering-service: all tests passed\n");
        return 0;
    }
    fprintf(stderr, "wagering-service: %d test(s) FAILED\n", failures);
    return 1;
}