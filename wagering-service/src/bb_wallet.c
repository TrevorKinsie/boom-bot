#include "bb_wallet.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "bb_util.h"

void bb_wallet_init(bb_wallet *w) {
    memset(w, 0, sizeof(*w));
}

void bb_wallet_free(bb_wallet *w) {
    free(w->sponsorships);
    w->sponsorships = NULL;
    w->sponsorship_count = 0;
}

static long long now_ts(void) {
    return (long long) time(NULL);
}

static void wallet_err(bb_wallet *w, const char *fmt, long long a1, long long a2) {
    snprintf(w->err, sizeof(w->err), fmt, a1, a2);
}

static void event_init(bb_event *out, int type, long long seq) {
    memset(out, 0, sizeof(*out));
    out->seq = seq;
    out->type = type;
    out->ts = now_ts();
}

int bb_wallet_apply(bb_wallet *w, const bb_event *ev) {
    switch (ev->type) {
        case BB_EV_WALLET_CREATED:
            if (w->exists) {
                wallet_err(w, "wallet already exists", 0, 0);
                return 0;
            }
            if (ev->amount < 0) {
                wallet_err(w, "starting balance must be non-negative", 0, 0);
                return 0;
            }
            w->exists = 1;
            w->balance = ev->amount;
            break;
        case BB_EV_FUNDS_DEBITED:
            if (!w->exists) {
                wallet_err(w, "wallet not provisioned", 0, 0);
                return 0;
            }
            if (ev->amount < 0) {
                wallet_err(w, "debit amount must be non-negative", 0, 0);
                return 0;
            }
            if (ev->amount > w->balance) {
                wallet_err(w, "insufficient funds: balance %.2f cannot cover debit %.2f",
                           (double) w->balance / BB_MONEY_SCALE,
                           (double) ev->amount / BB_MONEY_SCALE);
                return 0;
            }
            w->balance -= ev->amount;
            break;
        case BB_EV_FUNDS_CREDITED:
            if (!w->exists) {
                wallet_err(w, "wallet not provisioned", 0, 0);
                return 0;
            }
            if (ev->amount < 0) {
                wallet_err(w, "credit amount must be non-negative", 0, 0);
                return 0;
            }
            if (ev->amount > BB_MONEY_MAX - w->balance) {
                wallet_err(w, "credit would overflow the wallet", 0, 0);
                return 0;
            }
            w->balance += ev->amount;
            break;
        case BB_EV_WALLET_RESET:
            if (!w->exists) {
                wallet_err(w, "wallet not provisioned", 0, 0);
                return 0;
            }
            if (ev->amount < 0) {
                wallet_err(w, "reset balance must be non-negative", 0, 0);
                return 0;
            }
            w->balance = ev->amount;
            break;
        case BB_EV_FREE_SPIN_AWARDED:
            if (!w->exists) {
                wallet_err(w, "wallet not provisioned", 0, 0);
                return 0;
            }
            if (ev->count <= 0) {
                wallet_err(w, "free-spin award must be positive", 0, 0);
                return 0;
            }
            w->free_spins += ev->count;
            break;
        case BB_EV_FREE_SPIN_REDEEMED:
            if (!w->exists) {
                wallet_err(w, "wallet not provisioned", 0, 0);
                return 0;
            }
            if (w->free_spins <= 0) {
                wallet_err(w, "no free spins are available to redeem", 0, 0);
                return 0;
            }
            w->free_spins -= ev->count;
            break;
        case BB_EV_WAGER_RECORDED:
            if (!w->exists) {
                wallet_err(w, "wallet not provisioned", 0, 0);
                return 0;
            }
            if (ev->amount < 0 || ev->win < 0) {
                wallet_err(w, "wager amounts must be non-negative", 0, 0);
                return 0;
            }
            if (w->total_wagered > BB_MONEY_MAX - ev->amount ||
                w->total_won > BB_MONEY_MAX - ev->win) {
                wallet_err(w, "wager statistics would overflow", 0, 0);
                return 0;
            }
            w->total_wagered += ev->amount;
            w->total_won += ev->win;
            w->games_played++;
            if (ev->win > w->biggest_win) {
                w->biggest_win = ev->win;
            }
            break;
        case BB_EV_SPONSORSHIP_CREDITED:
            if (!w->exists) {
                wallet_err(w, "wallet not provisioned", 0, 0);
                return 0;
            }
            if (ev->amount < 0) {
                wallet_err(w, "sponsorship amount must be non-negative", 0, 0);
                return 0;
            }
            if (ev->amount > BB_MONEY_MAX - w->balance) {
                wallet_err(w, "sponsorship would overflow the wallet", 0, 0);
                return 0;
            }
            {
                bb_sponsorship *list = (bb_sponsorship *) realloc(
                        w->sponsorships,
                        (w->sponsorship_count + 1) * sizeof(bb_sponsorship));
                if (list == NULL) {
                    wallet_err(w, "out of memory recording sponsorship", 0, 0);
                    return 0;
                }
                w->sponsorships = list;
                bb_sponsorship *s = &list[w->sponsorship_count++];
                memset(s, 0, sizeof(*s));
                snprintf(s->ref, sizeof(s->ref), "%s", ev->ref);
                snprintf(s->sponsor, sizeof(s->sponsor), "%s", ev->sponsor);
                snprintf(s->purpose, sizeof(s->purpose), "%s", ev->purpose);
                s->amount = ev->amount;
                s->ts = ev->ts;
            }
            w->balance += ev->amount;
            break;
        default:
            wallet_err(w, "unknown event type %lld", (long long) ev->type, 0);
            return 0;
    }
    w->seq = ev->seq;
    return 1;
}

int bb_wallet_cmd_provision(bb_wallet *w, bb_money starting, bb_event *out) {
    event_init(out, BB_EV_WALLET_CREATED, w->seq + 1);
    out->amount = starting;
    return bb_wallet_apply(w, out);
}

int bb_wallet_cmd_debit(bb_wallet *w, bb_money amount, const char *reason, bb_event *out) {
    if (amount == 0) {
        wallet_err(w, "debit amount must be non-zero", 0, 0);
        return 0;
    }
    event_init(out, BB_EV_FUNDS_DEBITED, w->seq + 1);
    out->amount = amount;
    snprintf(out->reason, sizeof(out->reason), "%s", reason);
    return bb_wallet_apply(w, out);
}

int bb_wallet_cmd_credit(bb_wallet *w, bb_money amount, const char *reason, bb_event *out) {
    if (amount == 0) {
        wallet_err(w, "credit amount must be non-zero", 0, 0);
        return 0;
    }
    event_init(out, BB_EV_FUNDS_CREDITED, w->seq + 1);
    out->amount = amount;
    snprintf(out->reason, sizeof(out->reason), "%s", reason);
    return bb_wallet_apply(w, out);
}

int bb_wallet_cmd_reset(bb_wallet *w, bb_money reset_balance, bb_event *out) {
    event_init(out, BB_EV_WALLET_RESET, w->seq + 1);
    out->amount = reset_balance;
    return bb_wallet_apply(w, out);
}

int bb_wallet_cmd_award_spins(bb_wallet *w, long long count, bb_event *out) {
    if (count <= 0) {
        wallet_err(w, "free-spin award must be positive", 0, 0);
        return 0;
    }
    event_init(out, BB_EV_FREE_SPIN_AWARDED, w->seq + 1);
    out->count = count;
    return bb_wallet_apply(w, out);
}

int bb_wallet_cmd_redeem_spin(bb_wallet *w, bb_event *out) {
    event_init(out, BB_EV_FREE_SPIN_REDEEMED, w->seq + 1);
    out->count = 1;
    return bb_wallet_apply(w, out);
}

int bb_wallet_cmd_wager(bb_wallet *w, bb_money wager, bb_money win, const char *game, bb_event *out) {
    event_init(out, BB_EV_WAGER_RECORDED, w->seq + 1);
    out->amount = wager;
    out->win = win;
    snprintf(out->reason, sizeof(out->reason), "%s", game);
    return bb_wallet_apply(w, out);
}

int bb_wallet_cmd_sponsor(bb_wallet *w, bb_money amount, const char *sponsor,
                          const char *purpose, const char *ref, bb_event *out) {
    if (amount <= 0) {
        wallet_err(w, "sponsorship amount must be positive", 0, 0);
        return 0;
    }
    event_init(out, BB_EV_SPONSORSHIP_CREDITED, w->seq + 1);
    out->amount = amount;
    snprintf(out->sponsor, sizeof(out->sponsor), "%s", sponsor);
    snprintf(out->purpose, sizeof(out->purpose), "%s", purpose);
    snprintf(out->ref, sizeof(out->ref), "%s", ref);
    return bb_wallet_apply(w, out);
}

/* ------------------------------------------------------- event codec --- */

static const char *event_type_name(int type) {
    switch (type) {
        case BB_EV_WALLET_CREATED: return "WALLET_CREATED";
        case BB_EV_FUNDS_DEBITED: return "FUNDS_DEBITED";
        case BB_EV_FUNDS_CREDITED: return "FUNDS_CREDITED";
        case BB_EV_WALLET_RESET: return "WALLET_RESET";
        case BB_EV_FREE_SPIN_AWARDED: return "FREE_SPIN_AWARDED";
        case BB_EV_FREE_SPIN_REDEEMED: return "FREE_SPIN_REDEEMED";
        case BB_EV_WAGER_RECORDED: return "WAGER_RECORDED";
        case BB_EV_SPONSORSHIP_CREDITED: return "SPONSORSHIP_CREDITED";
        default: return "UNKNOWN";
    }
}

static int event_type_from_name(const char *name, int *out) {
    struct {
        const char *name;
        int type;
    } table[] = {
        {"WALLET_CREATED", BB_EV_WALLET_CREATED},
        {"FUNDS_DEBITED", BB_EV_FUNDS_DEBITED},
        {"FUNDS_CREDITED", BB_EV_FUNDS_CREDITED},
        {"WALLET_RESET", BB_EV_WALLET_RESET},
        {"FREE_SPIN_AWARDED", BB_EV_FREE_SPIN_AWARDED},
        {"FREE_SPIN_REDEEMED", BB_EV_FREE_SPIN_REDEEMED},
        {"WAGER_RECORDED", BB_EV_WAGER_RECORDED},
        {"SPONSORSHIP_CREDITED", BB_EV_SPONSORSHIP_CREDITED},
    };
    for (size_t i = 0; i < sizeof(table) / sizeof(table[0]); i++) {
        if (strcmp(name, table[i].name) == 0) {
            *out = table[i].type;
            return 1;
        }
    }
    return 0;
}

bb_jval *bb_event_to_json(const bb_event *ev) {
    bb_jval *v = bb_json_object();
    bb_json_put(v, "seq", bb_json_int(ev->seq));
    bb_json_put(v, "type", bb_json_str(event_type_name(ev->type)));
    bb_json_put(v, "ts", bb_json_int(ev->ts));
    if (ev->amount != 0 || ev->type == BB_EV_WALLET_CREATED || ev->type == BB_EV_WALLET_RESET) {
        char tmp[32];
        bb_money_fmt(ev->amount, tmp);
        bb_json_put(v, "amount", bb_json_str(tmp));
    }
    if (ev->win != 0) {
        char tmp[32];
        bb_money_fmt(ev->win, tmp);
        bb_json_put(v, "win", bb_json_str(tmp));
    }
    if (ev->count != 0) {
        bb_json_put(v, "count", bb_json_int(ev->count));
    }
    if (ev->reason[0] != '\0') {
        bb_json_put(v, "reason", bb_json_str(ev->reason));
    }
    if (ev->sponsor[0] != '\0') {
        bb_json_put(v, "sponsor", bb_json_str(ev->sponsor));
    }
    if (ev->purpose[0] != '\0') {
        bb_json_put(v, "purpose", bb_json_str(ev->purpose));
    }
    if (ev->ref[0] != '\0') {
        bb_json_put(v, "ref", bb_json_str(ev->ref));
    }
    return v;
}

int bb_event_from_json(const bb_jval *v, bb_event *out) {
    memset(out, 0, sizeof(*out));
    const char *type = bb_json_strval(bb_json_get(v, "type"), "");
    if (!event_type_from_name(type, &out->type)) {
        return 0;
    }
    out->seq = bb_json_intval(bb_json_get(v, "seq"), 0);
    out->ts = bb_json_intval(bb_json_get(v, "ts"), 0);
    bb_money amount = 0, win = 0;
    if (!bb_money_parse(bb_json_strval(bb_json_get(v, "amount"), "0"), &amount)) {
        return 0;
    }
    if (!bb_money_parse(bb_json_strval(bb_json_get(v, "win"), "0"), &win)) {
        return 0;
    }
    out->amount = amount;
    out->win = win;
    out->count = bb_json_intval(bb_json_get(v, "count"), 0);
    snprintf(out->reason, sizeof(out->reason), "%s",
             bb_json_strval(bb_json_get(v, "reason"), ""));
    snprintf(out->sponsor, sizeof(out->sponsor), "%s",
             bb_json_strval(bb_json_get(v, "sponsor"), ""));
    snprintf(out->purpose, sizeof(out->purpose), "%s",
             bb_json_strval(bb_json_get(v, "purpose"), ""));
    snprintf(out->ref, sizeof(out->ref), "%s",
             bb_json_strval(bb_json_get(v, "ref"), ""));
    return 1;
}

/* ------------------------------------------------------ snapshot codec --- */

bb_jval *bb_wallet_to_json(const bb_wallet *w) {
    bb_jval *v = bb_json_object();
    char tmp[32];
    bb_json_put(v, "exists", bb_json_bool(w->exists));
    bb_money_fmt(w->balance, tmp);
    bb_json_put(v, "balance", bb_json_str(tmp));
    bb_money_fmt(w->total_wagered, tmp);
    bb_json_put(v, "total_wagered", bb_json_str(tmp));
    bb_money_fmt(w->total_won, tmp);
    bb_json_put(v, "total_won", bb_json_str(tmp));
    bb_money_fmt(w->biggest_win, tmp);
    bb_json_put(v, "biggest_win", bb_json_str(tmp));
    bb_json_put(v, "free_spins", bb_json_int(w->free_spins));
    bb_json_put(v, "games_played", bb_json_int(w->games_played));
    bb_json_put(v, "seq", bb_json_int(w->seq));
    bb_jval *sponsors = bb_json_array();
    for (size_t i = 0; i < w->sponsorship_count; i++) {
        bb_jval *s = bb_json_object();
        bb_json_put(s, "ref", bb_json_str(w->sponsorships[i].ref));
        bb_json_put(s, "sponsor", bb_json_str(w->sponsorships[i].sponsor));
        bb_json_put(s, "purpose", bb_json_str(w->sponsorships[i].purpose));
        char amt[32];
        bb_money_fmt(w->sponsorships[i].amount, amt);
        bb_json_put(s, "amount", bb_json_str(amt));
        bb_json_put(s, "ts", bb_json_int(w->sponsorships[i].ts));
        bb_json_append(sponsors, s);
    }
    bb_json_put(v, "sponsorships", sponsors);
    return v;
}

int bb_wallet_from_json(const bb_jval *v, bb_wallet *w) {
    bb_wallet_init(w);
    w->exists = bb_json_boolval(bb_json_get(v, "exists"), 0);
    bb_money balance = 0, wagered = 0, won = 0, biggest = 0;
    if (!bb_money_parse(bb_json_strval(bb_json_get(v, "balance"), "0"), &balance) ||
        !bb_money_parse(bb_json_strval(bb_json_get(v, "total_wagered"), "0"), &wagered) ||
        !bb_money_parse(bb_json_strval(bb_json_get(v, "total_won"), "0"), &won) ||
        !bb_money_parse(bb_json_strval(bb_json_get(v, "biggest_win"), "0"), &biggest)) {
        return 0;
    }
    w->balance = balance;
    w->total_wagered = wagered;
    w->total_won = won;
    w->biggest_win = biggest;
    w->free_spins = bb_json_intval(bb_json_get(v, "free_spins"), 0);
    w->games_played = bb_json_intval(bb_json_get(v, "games_played"), 0);
    w->seq = bb_json_intval(bb_json_get(v, "seq"), 0);
    bb_jval *sponsors = bb_json_get(v, "sponsorships");
    if (sponsors != NULL && sponsors->type == BB_JARRAY) {
        for (size_t i = 0; i < sponsors->u.arr.n; i++) {
            bb_jval *s = sponsors->u.arr.items[i];
            bb_sponsorship *list = (bb_sponsorship *) realloc(
                    w->sponsorships, (w->sponsorship_count + 1) * sizeof(bb_sponsorship));
            if (list == NULL) {
                bb_wallet_free(w);
                return 0;
            }
            w->sponsorships = list;
            bb_sponsorship *sp = &list[w->sponsorship_count++];
            memset(sp, 0, sizeof(*sp));
            snprintf(sp->ref, sizeof(sp->ref), "%s", bb_json_strval(bb_json_get(s, "ref"), ""));
            snprintf(sp->sponsor, sizeof(sp->sponsor), "%s",
                     bb_json_strval(bb_json_get(s, "sponsor"), ""));
            snprintf(sp->purpose, sizeof(sp->purpose), "%s",
                     bb_json_strval(bb_json_get(s, "purpose"), ""));
            bb_money amt = 0;
            if (!bb_money_parse(bb_json_strval(bb_json_get(s, "amount"), "0"), &amt)) {
                bb_wallet_free(w);
                return 0;
            }
            sp->amount = amt;
            sp->ts = bb_json_intval(bb_json_get(s, "ts"), 0);
        }
    }
    return 1;
}