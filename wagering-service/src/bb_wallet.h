#ifndef BB_WALLET_H
#define BB_WALLET_H

#include <stddef.h>
#include <stdint.h>

#include "bb_json.h"
#include "bb_money.h"

/*
 * bb_wallet: the event-sourced wallet aggregate, the C port of the Python
 * wagering context's Wallet.
 *
 * A wallet never mutates a stored balance directly: every state transition
 * is a domain event applied through bb_wallet_apply, mirroring the Python
 * aggregate. Invariants preserved by the commands:
 *   - a debit may never overdraw the balance (insufficient funds),
 *   - a free spin may never be redeemed below zero,
 *   - sponsored credits are recorded with their sponsor for auditability.
 *
 * Commands are pure: they produce the event (validated against the current
 * state) and apply it in memory; the caller persists it to the store.
 */

#define BB_WALLET_USER_MAX 64
#define BB_WALLET_REF_MAX 63
#define BB_WALLET_TEXT_MAX 127
#define BB_WALLET_ERR_MAX 160

typedef enum {
    BB_EV_WALLET_CREATED = 1,
    BB_EV_FUNDS_DEBITED,
    BB_EV_FUNDS_CREDITED,
    BB_EV_WALLET_RESET,
    BB_EV_FREE_SPIN_AWARDED,
    BB_EV_FREE_SPIN_REDEEMED,
    BB_EV_WAGER_RECORDED,
    BB_EV_SPONSORSHIP_CREDITED
} bb_event_type;

typedef struct {
    long long seq;      /* sequence number within the wallet's event log */
    int type;           /* bb_event_type */
    long long ts;       /* unix seconds */
    bb_money amount;    /* start / debit / credit / reset / wager / sponsorship */
    bb_money win;       /* wager-record win amount */
    long long count;    /* free spins */
    char reason[BB_WALLET_TEXT_MAX + 1];
    char sponsor[BB_WALLET_TEXT_MAX + 1];
    char purpose[BB_WALLET_TEXT_MAX + 1];
    char ref[BB_WALLET_REF_MAX + 1];
} bb_event;

typedef struct {
    char ref[BB_WALLET_REF_MAX + 1];
    char sponsor[BB_WALLET_TEXT_MAX + 1];
    char purpose[BB_WALLET_TEXT_MAX + 1];
    bb_money amount;
    long long ts;
} bb_sponsorship;

typedef struct {
    int exists;
    bb_money balance;
    bb_money total_wagered;
    bb_money total_won;
    bb_money biggest_win;
    long long free_spins;
    long long games_played;
    long long seq;      /* last applied event sequence */
    bb_sponsorship *sponsorships;
    size_t sponsorship_count;
    char err[BB_WALLET_ERR_MAX + 1];
} bb_wallet;

void bb_wallet_init(bb_wallet *w);
void bb_wallet_free(bb_wallet *w);

/* Fold one event into the state; returns 0 and sets w->err when the event
   contradicts an invariant (e.g. a debit that would overdraw a replayed log). */
int bb_wallet_apply(bb_wallet *w, const bb_event *ev);

/* Command+apply helpers; each returns 0 and sets w->err when rejected. */
int bb_wallet_cmd_provision(bb_wallet *w, bb_money starting, bb_event *out);
int bb_wallet_cmd_debit(bb_wallet *w, bb_money amount, const char *reason, bb_event *out);
int bb_wallet_cmd_credit(bb_wallet *w, bb_money amount, const char *reason, bb_event *out);
int bb_wallet_cmd_reset(bb_wallet *w, bb_money reset_balance, bb_event *out);
int bb_wallet_cmd_award_spins(bb_wallet *w, long long count, bb_event *out);
int bb_wallet_cmd_redeem_spin(bb_wallet *w, bb_event *out);
int bb_wallet_cmd_wager(bb_wallet *w, bb_money wager, bb_money win, const char *game, bb_event *out);
int bb_wallet_cmd_sponsor(bb_wallet *w, bb_money amount, const char *sponsor,
                          const char *purpose, const char *ref, bb_event *out);

/* Event <-> JSON codecs (used by the encrypted store). */
bb_jval *bb_event_to_json(const bb_event *ev);
int bb_event_from_json(const bb_jval *v, bb_event *out);

/* Snapshot <-> JSON codecs. */
bb_jval *bb_wallet_to_json(const bb_wallet *w);
int bb_wallet_from_json(const bb_jval *v, bb_wallet *w);

#endif /* BB_WALLET_H */