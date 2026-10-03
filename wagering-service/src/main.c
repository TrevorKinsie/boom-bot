#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include "bb_cipher.h"
#include "bb_main.h"
#include "bb_util.h"
#include "bb_wallet.h"

/*
 * JSON-lines protocol for the wagering service, mirroring the shape of the
 * JVM decision engine: one request object per line on stdin, one response
 * object per line on stdout.
 *
 * Requests:  {"id":"...", "op":"<op>", "user":"<user>", ...args }
 * Success:   {"id":"...", "ok":true,  "data":{...}}
 * Failure:   {"id":"...", "ok":false, "error":{"code":"...","message":"..."}}
 *
 * Ops:
 *   wallet_provision  {user, starting_balance}
 *   wallet_get        {user}
 *   wallet_debit      {user, amount, reason}
 *   wallet_credit     {user, amount, reason}
 *   wallet_reset      {user, reset_balance}
 *   free_spins_award  {user, count}
 *   free_spins_redeem {user}
 *   wager_record      {user, wager, win, game}
 *   sponsor_start     {user, sponsor, amount, purpose, ref}
 *   sponsorships_list {user}
 *   crypto_selfcheck  {}
 */

static const char *TAG_USER = "user";
static const char *TAG_OP = "op";

typedef struct {
    char user[BB_WALLET_USER_MAX + 1];
    char text[BB_WALLET_TEXT_MAX + 1];
    char ref[BB_WALLET_REF_MAX + 1];
    bb_money amount;
    bb_money win;
    long long count;
} bb_op_args;

static int take_user(const bb_jval *req, char *out, size_t n) {
    const char *user = bb_json_strval(bb_json_get(req, TAG_USER), "");
    if (*user == '\0') {
        return 0;
    }
    snprintf(out, n, "%s", user);
    return 1;
}

static bb_jval *error_response(const char *id, const char *code, const char *message) {
    bb_jval *resp = bb_json_object();
    bb_json_put(resp, "id", bb_json_str(id));
    bb_json_put(resp, "ok", bb_json_bool(0));
    bb_jval *err = bb_json_object();
    bb_json_put(err, "code", bb_json_str(code));
    bb_json_put(err, "message", bb_json_str(message));
    bb_json_put(resp, "error", err);
    return resp;
}

static bb_jval *ok_response(const char *id, bb_jval *data) {
    bb_jval *resp = bb_json_object();
    bb_json_put(resp, "id", bb_json_str(id));
    bb_json_put(resp, "ok", bb_json_bool(1));
    bb_json_put(resp, "data", data);
    return resp;
}

/* Fold the wallet state into the data payload of a successful op. */
static bb_jval *wallet_data(const bb_wallet *w) {
    bb_jval *data = bb_wallet_to_json(w);
    return data;
}

int bb_handle_line(const char *line, char *out, size_t out_size, bb_store *svc) {
    bb_buf sink;
    bb_buf_init(&sink);

    char err_tmp[128];
    bb_jval *req = bb_json_parse_err(line, err_tmp, sizeof(err_tmp));
    if (req == NULL) {
        bb_jval *resp = error_response("", "parse_error", err_tmp);
        bb_json_serialize(resp, &sink);
        bb_json_free(resp);
        bb_buf_push_c(&sink, '\0');
        snprintf(out, out_size, "%s", (char *) sink.data);
        bb_buf_free(&sink);
        return -1;
    }

    const char *id = bb_json_strval(bb_json_get(req, "id"), "");
    const char *op = bb_json_strval(bb_json_get(req, TAG_OP), "");
    bb_jval *resp = NULL;

    if (strcmp(op, "crypto_selfcheck") == 0) {
        int ok = bb64_selfcheck();
        if (!ok) {
            resp = error_response(id, "crypto_failed", "BB64 known-answer self-test failed");
        } else {
            bb_jval *data = bb_json_object();
            bb_json_put(data, "cipher", bb_json_str("bb64"));
            bb_json_put(data, "kat", bb_json_str("ok"));
            resp = ok_response(id, data);
        }
    } else {
        char user[BB_WALLET_USER_MAX + 1] = {0};
        if (!take_user(req, user, sizeof(user))) {
            resp = error_response(id, "missing_user", "a 'user' field is required");
        } else {
            bb_wallet w;
            int loaded = bb_store_load(svc, user, &w);
            if (loaded < 0) {
                resp = error_response(id, "store_corrupt", svc->err);
                bb_json_free(req);
                bb_json_serialize(resp, &sink);
                bb_json_free(resp);
                bb_buf_push_c(&sink, '\0');
                snprintf(out, out_size, "%s", (char *) sink.data);
                bb_buf_free(&sink);
                return 0;
            }
            if (!w.exists && strcmp(op, "wallet_provision") != 0) {
                resp = error_response(id, "no_wallet", "wallet has not been provisioned");
                bb_wallet_free(&w);
            } else if (strcmp(op, "wallet_provision") == 0) {
                bb_money starting = 0;
                if (!bb_money_parse(bb_json_strval(bb_json_get(req, "starting_balance"), "0"),
                                    &starting)) {
                    resp = error_response(id, "invalid_amount", "starting_balance is not a valid amount");
                } else {
                    bb_event ev;
                    if (!bb_wallet_cmd_provision(&w, starting, &ev)) {
                        resp = error_response(id, strstr(w.err, "already exists") ? "wallet_exists" : "wallet_error", w.err);
                    } else if (!bb_store_append(svc, user, &ev)) {
                        resp = error_response(id, "store_error", svc->err);
                    } else {
                        resp = ok_response(id, wallet_data(&w));
                    }
                }
                bb_wallet_free(&w);
            } else if (strcmp(op, "wallet_get") == 0) {
                resp = ok_response(id, wallet_data(&w));
                bb_wallet_free(&w);
            } else if (strcmp(op, "wallet_debit") == 0 || strcmp(op, "wallet_credit") == 0) {
                bb_money amount = 0;
                if (!bb_money_parse(bb_json_strval(bb_json_get(req, "amount"), ""), &amount)) {
                    resp = error_response(id, "invalid_amount", "amount is not a valid money value");
                } else {
                    const char *reason = bb_json_strval(bb_json_get(req, "reason"), "wallet_operation");
                    bb_event ev;
                    int ok = strcmp(op, "wallet_debit") == 0
                            ? bb_wallet_cmd_debit(&w, amount, reason, &ev)
                            : bb_wallet_cmd_credit(&w, amount, reason, &ev);
                    if (!ok) {
                        resp = error_response(id, strstr(w.err, "insufficient") ? "insufficient_funds" : "wallet_error", w.err);
                    } else if (!bb_store_append(svc, user, &ev)) {
                        resp = error_response(id, "store_error", svc->err);
                    } else {
                        resp = ok_response(id, wallet_data(&w));
                    }
                }
                bb_wallet_free(&w);
            } else if (strcmp(op, "wallet_reset") == 0) {
                bb_money reset_balance = 0;
                if (!bb_money_parse(bb_json_strval(bb_json_get(req, "reset_balance"), "0"),
                                    &reset_balance)) {
                    resp = error_response(id, "invalid_amount", "reset_balance is not a valid amount");
                } else {
                    bb_event ev;
                    if (!bb_wallet_cmd_reset(&w, reset_balance, &ev) ||
                        !bb_store_append(svc, user, &ev)) {
                        resp = error_response(id, "wallet_error", w.err);
                    } else {
                        resp = ok_response(id, wallet_data(&w));
                    }
                }
                bb_wallet_free(&w);
            } else if (strcmp(op, "free_spins_award") == 0) {
                long long count = bb_json_intval(bb_json_get(req, "count"), 0);
                bb_event ev;
                if (!bb_wallet_cmd_award_spins(&w, count, &ev) ||
                    !bb_store_append(svc, user, &ev)) {
                    resp = error_response(id, "wallet_error", w.err);
                } else {
                    resp = ok_response(id, wallet_data(&w));
                }
                bb_wallet_free(&w);
            } else if (strcmp(op, "free_spins_redeem") == 0) {
                bb_event ev;
                if (!bb_wallet_cmd_redeem_spin(&w, &ev) ||
                    !bb_store_append(svc, user, &ev)) {
                    resp = error_response(id, strstr(w.err, "no free spins") ? "no_free_spins" : "wallet_error", w.err);
                } else {
                    resp = ok_response(id, wallet_data(&w));
                }
                bb_wallet_free(&w);
            } else if (strcmp(op, "wager_record") == 0) {
                bb_money wager = 0, win = 0;
                if (!bb_money_parse(bb_json_strval(bb_json_get(req, "wager"), ""), &wager) ||
                    !bb_money_parse(bb_json_strval(bb_json_get(req, "win"), "0"), &win)) {
                    resp = error_response(id, "invalid_amount", "wager/win are not valid amounts");
                } else {
                    const char *game = bb_json_strval(bb_json_get(req, "game"), "unknown");
                    bb_event ev;
                    if (!bb_wallet_cmd_wager(&w, wager, win, game, &ev) ||
                        !bb_store_append(svc, user, &ev)) {
                        resp = error_response(id, "wallet_error", w.err);
                    } else {
                        resp = ok_response(id, wallet_data(&w));
                    }
                }
                bb_wallet_free(&w);
            } else if (strcmp(op, "sponsor_start") == 0) {
                bb_money amount = 0;
                const char *sponsor = bb_json_strval(bb_json_get(req, "sponsor"), "");
                const char *purpose = bb_json_strval(bb_json_get(req, "purpose"), "sponsorship");
                const char *ref = bb_json_strval(bb_json_get(req, "ref"), "");
                if (!bb_money_parse(bb_json_strval(bb_json_get(req, "amount"), ""), &amount)) {
                    resp = error_response(id, "invalid_amount", "amount is not a valid money value");
                } else if (*sponsor == '\0' || *ref == '\0') {
                    resp = error_response(id, "missing_field", "sponsor and ref are required");
                } else {
                    bb_event ev;
                    if (!bb_wallet_cmd_sponsor(&w, amount, sponsor, purpose, ref, &ev) ||
                        !bb_store_append(svc, user, &ev)) {
                        resp = error_response(id, "wallet_error", w.err);
                    } else {
                        resp = ok_response(id, wallet_data(&w));
                    }
                }
                bb_wallet_free(&w);
            } else if (strcmp(op, "sponsorships_list") == 0) {
                resp = ok_response(id, wallet_data(&w));
                bb_wallet_free(&w);
            } else {
                resp = error_response(id, "unknown_op", "no such op");
                bb_wallet_free(&w);
            }
        }
    }

    bb_json_free(req);
    bb_json_serialize(resp, &sink);
    bb_json_free(resp);
    bb_buf_push_c(&sink, '\0');
    snprintf(out, out_size, "%s", (char *) sink.data);
    bb_buf_free(&sink);
    return 0;
}

#ifndef BB_TEST
int main(void) {
    const char *dir = getenv("WAGERING_SERVICE_DATA_DIR");
    if (dir == NULL || *dir == '\0') {
        dir = "data";
    }
    mkdir(dir, 0700); /* ignore EEXIST; other failures surface on first write */
    const char *fsync_raw = getenv("WAGERING_SERVICE_FSYNC");
    int use_fsync = (fsync_raw != NULL && strcmp(fsync_raw, "0") == 0) ? 0 : 1;

    const char *key_hex = getenv("WAGERING_SERVICE_KEY");
    uint8_t key[32];
    if (key_hex == NULL || bb_hex_decode(key_hex, strlen(key_hex), key) != 32) {
        static const uint8_t default_key[32] = {
            0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef,
            0xfe, 0xdc, 0xba, 0x98, 0x76, 0x54, 0x32, 0x10,
            0x0f, 0x1e, 0x2d, 0x3c, 0x4b, 0x5a, 0x69, 0x78,
            0x87, 0x96, 0xa5, 0xb4, 0xc3, 0xd2, 0xe1, 0xf0};
        fprintf(stderr,
                "[warn] WAGERING_SERVICE_KEY unset or invalid; using the built-in default key.\n"
                "[warn] Never run with the default key outside local development.\n");
        memcpy(key, default_key, 32);
    }

    bb_store svc;
    bb_store_init(&svc, key, key + 16, dir, use_fsync);

    if (!bb64_selfcheck()) {
        fprintf(stderr, "[fatal] BB64 known-answer self-test failed; refusing to serve.\n");
        return 1;
    }

    char line[8192];
    char out[BB_PROTO_OUT_SIZE];
    while (fgets(line, sizeof(line), stdin) != NULL) {
        size_t n = strlen(line);
        while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r')) {
            line[--n] = '\0';
        }
        if (n == 0) {
            continue;
        }
        bb_handle_line(line, out, sizeof(out), &svc);
        puts(out);
        fflush(stdout);
    }
    return 0;
}
#endif /* BB_TEST */