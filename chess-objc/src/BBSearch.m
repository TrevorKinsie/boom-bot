/* BBSearch.m — negamax alpha-beta search with PVS, iterative deepening,
 * quiescence, null-move pruning, killer moves, MVV-LVA ordering and a
 * depth-preferred transposition table.
 *
 * The hot loop is plain C over a small engine struct so the compiler can
 * fully optimise it; surrounding it is a thin Objective-C class that owns
 * the state and drives the search on its caller's thread.
 */
#include "BBSearch.h"

#include <pthread.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "BBEval.h"

#define BB_MATE 30000
#define BB_INF  31000

/* TT entry flag bits (two-bit record shape). */
#define BB_TT_NONE   0
#define BB_TT_EXACT  1
#define BB_TT_UPPER  2   /* score <= alpha (fail-low bound) */
#define BB_TT_LOWER  3   /* score >= beta  (fail-high bound) */

#define BB_TT_DEF_BITS 18
#define BB_TT_MAX_BITS 25
#define BB_TT_MIN_BITS 8

#define BB_NODE_CHUNK 2048
#define BB_HASH_GEN_BITS 6
#define BB_HASH_GEN_MASK ((1u << BB_HASH_GEN_BITS) - 1u)

#define BB_PLY_MAX 512

typedef struct BBTEntry {
    uint64_t key;
    int32_t  score;
    uint16_t move;
    uint8_t  depth;
    uint8_t  flagsGen;   /* flags(2) | generation(6) */
} BBTEntry;

typedef struct BBTTable {
    BBTEntry *entries;
    uint64_t  mask;
    uint8_t   gen;
} BBTTable;

struct BBEngine {
    BBCore core;
    BBCoreUndo undo[BB_PLY_MAX + 4];
    BBMove killers[BB_PLY_MAX][2];
    BBTTable tt;
    int stop;

    int32_t  rootMoves[256];
    BBMove   rootMoveList[256];
    int      rootCount;
    uint16_t rootBest;

    int      depthLimit;
    int64_t  moveTimeMs;
    int64_t  ourTimeMs;
    int64_t  incMs;
    int64_t  nodeLimit;

    int64_t  nodes;
    int64_t  startMs;
    int64_t  softDeadline;   /* -1 = none */
    int64_t  hardDeadline;   /* -1 = none */
    int32_t  lastScore;
    char     bestUci[8];
    int      searchDone;
    int      quiet;
};

/* ------------------------------------------------------------------ */
/* Time helpers                                                       */
/* ------------------------------------------------------------------ */

static int64_t nowMs(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000 + (int64_t)(ts.tv_nsec / 1000000);
}

/* ------------------------------------------------------------------ */
/* Transposition table                                                */
/* ------------------------------------------------------------------ */

static void ttInit(BBTTable *t, int bits)
{
    size_t count;
    if (bits < BB_TT_MIN_BITS) {
        bits = BB_TT_MIN_BITS;
    }
    if (bits > BB_TT_MAX_BITS) {
        bits = BB_TT_MAX_BITS;
    }
    count = (size_t)1 << bits;
    t->entries = (BBTEntry *)calloc(count, sizeof(BBTEntry));
    if (t->entries == NULL) {
        count = 0;
    }
    t->mask = count > 0 ? (uint64_t)(count - 1) : 0;
    t->gen = 1;
}

static void ttNewGame(BBTTable *t)
{
    t->gen = (uint8_t)((t->gen + 1) & BB_HASH_GEN_MASK);
    if (t->gen == 0) {
        t->gen = 1;
    }
    if (t->entries != NULL && t->mask > 0 && (t->gen & 3) == 0) {
        memset(t->entries, 0, ((size_t)t->mask + 1) * sizeof(BBTEntry));
    }
}

static inline int ttProbe(const BBTTable *t, uint64_t key, BBTEntry *out)
{
    BBTEntry *e;
    if (t->mask == 0) {
        return 0;
    }
    e = &t->entries[key & t->mask];
    if (e->key == key && (e->flagsGen & 3) != BB_TT_NONE) {
        *out = *e;
        return 1;
    }
    return 0;
}

static inline uint16_t ttProbeMove(const BBTTable *t, uint64_t key)
{
    BBTEntry *e;
    if (t->mask == 0) {
        return 0;
    }
    e = &t->entries[key & t->mask];
    if (e->key == key && (e->flagsGen & 3) != BB_TT_NONE) {
        return e->move;
    }
    return 0;
}

static inline void ttStore(BBTTable *t, uint64_t key, BBMove move, int depth,
                           int flags, int32_t score)
{
    BBTEntry *e;
    if (t->mask == 0) {
        return;
    }
    e = &t->entries[key & t->mask];
    if (e->key == key &&
        (e->flagsGen & 3) == BB_TT_EXACT &&
        e->depth > depth) {
        return;
    }
    e->key = key;
    e->score = score;
    e->move = move;
    e->depth = (uint8_t)depth;
    e->flagsGen = (uint8_t)((uint8_t)flags | (uint8_t)(t->gen << 2));
}

/* ------------------------------------------------------------------ */
/* Static evaluation wrapper (side-to-move perspective)               */
/* ------------------------------------------------------------------ */

static inline int32_t evalSide(const BBCore *b)
{
    int32_t white = bbEvaluate(b);
    return (b->stm == BB_WHITE) ? white : -white;
}

/* ------------------------------------------------------------------ */
/* Move ordering                                                      */
/* ------------------------------------------------------------------ */

static const int gVictimValue[8] = {
    0, 1, 3, 3, 5, 9, 0, 0
};

static int32_t orderScore(const struct BBEngine *e, BBMove m, uint16_t ttMove,
                          int ply)
{
    int flags = bbMoveFlags(m);
    int32_t s = 0;
    if (m == ttMove && ttMove != 0) {
        return 2000000;
    }
    if (bbMoveIsCapture(m)) {
        int victim = BB_PAWN;
        if (flags != BB_MOVE_EP) {
            victim = bbTypeOf(e->core.squares[bbMoveTo(m)]);
        }
        s += 1000000 + gVictimValue[victim] * 16 - bbTypeOf(e->core.squares[bbMoveFrom(m)]);
    } else if (flags >= BB_MOVE_PROMO_Q && flags <= BB_MOVE_PROMO_N) {
        s += 500000;
    }
    if (ply < BB_PLY_MAX) {
        if (m == e->killers[ply][0]) {
            s += 250000;
        } else if (m == e->killers[ply][1]) {
            s += 125000;
        }
    }
    return s;
}

/* Insertion sort over (move, score) pairs, descending by score. */
static void sortMoves(BBMove *moves, int n, uint16_t ttMove, int ply,
                      const struct BBEngine *e)
{
    int32_t scores[256];
    int i;
    for (i = 0; i < n; i++) {
        scores[i] = orderScore(e, moves[i], ttMove, ply);
    }
    for (i = 1; i < n; i++) {
        BBMove m = moves[i];
        int32_t s = scores[i];
        int j = i - 1;
        while (j >= 0 && scores[j] < s) {
            moves[j + 1] = moves[j];
            scores[j + 1] = scores[j];
            j--;
        }
        moves[j + 1] = m;
        scores[j + 1] = s;
    }
}

/* ------------------------------------------------------------------ */
/* Quiescence search                                                  */
/* ------------------------------------------------------------------ */

static int32_t qsearch(struct BBEngine *e, int32_t alpha, int32_t beta,
                       int ply)
{
    int32_t stand;
    int n;
    BBMove moves[256];
    int i;

    e->nodes++;
    if ((e->nodes & (BB_NODE_CHUNK - 1)) == 0 &&
        __atomic_load_n(&e->stop, __ATOMIC_RELAXED)) {
        return 0;
    }

    stand = evalSide(&e->core);
    if (stand >= beta) {
        return stand;
    }
    if (stand > alpha) {
        alpha = stand;
    }

    n = bbGenPseudo(&e->core, moves);
    {
        int w = 0;
        for (i = 0; i < n; i++) {
            if (bbMoveIsCapture(moves[i])) {
                moves[w++] = moves[i];
            }
        }
        n = w;
    }
    sortMoves(moves, n, 0, ply, e);

    for (i = 0; i < n; i++) {
        BBCoreUndo u;
        int32_t score;
        int moverColor = e->core.stm;
        bbCoreMake(&e->core, moves[i], &u);
        if (bbInCheckSide(&e->core, moverColor)) {
            bbCoreUnmake(&e->core, &u);
            continue;
        }
        score = -qsearch(e, -beta, -alpha, ply + 1);
        bbCoreUnmake(&e->core, &u);
        if (__atomic_load_n(&e->stop, __ATOMIC_RELAXED)) {
            return 0;
        }
        if (score >= beta) {
            return score;
        }
        if (score > alpha) {
            alpha = score;
        }
    }
    return alpha;
}

/* ------------------------------------------------------------------ */
/* Main alpha-beta search                                             */
/* ------------------------------------------------------------------ */

static int hasNonPawnMaterial(const struct BBEngine *e)
{
    int i;
    for (i = 0; i < 64; i++) {
        BBPiece pc = e->core.squares[i];
        if (pc != BB_EMPTY && bbColorOf(pc) == e->core.stm) {
            int t = bbTypeOf(pc);
            if (t != BB_PAWN && t != BB_KING) {
                return 1;
            }
        }
    }
    return 0;
}

static int32_t negamax(struct BBEngine *e, int32_t depth, int32_t alpha,
                       int32_t beta, int ply)
{
    int inCheck;
    int n;
    BBMove moves[256];
    BBTEntry entry;
    int ttHit;
    uint16_t ttMove;
    int32_t best;
    BBMove bestMove = 0;
    int i;
    int moveCount = 0;

    e->nodes++;
    if ((e->nodes & (BB_NODE_CHUNK - 1)) == 0) {
        if (__atomic_load_n(&e->stop, __ATOMIC_RELAXED) ||
            (e->hardDeadline >= 0 && nowMs() >= e->hardDeadline) ||
            (e->nodeLimit > 0 && e->nodes >= e->nodeLimit)) {
            __atomic_store_n(&e->stop, 1, __ATOMIC_RELAXED);
            return 0;
        }
    }

    if (ply >= BB_PLY_MAX) {
        return evalSide(&e->core);
    }
    if (ply > 0 && (bbIsRepetition(&e->core) || bbIsFiftyMove(&e->core) ||
                    bbInsufficientMaterial(&e->core))) {
        return 0;
    }

    ttHit = ttProbe(&e->tt, e->core.key, &entry);
    if (ttHit && entry.depth >= depth) {
        int32_t v = entry.score;
        if ((entry.flagsGen & 3) == BB_TT_EXACT) {
            return v;
        }
        if ((entry.flagsGen & 3) == BB_TT_UPPER && v <= alpha) {
            return v;
        }
        if ((entry.flagsGen & 3) == BB_TT_LOWER && v >= beta) {
            return v;
        }
    }
    ttMove = ttHit ? entry.move : (uint16_t)0;

    inCheck = bbInCheck(&e->core);

    if (depth <= 0) {
        return qsearch(e, alpha, beta, ply);
    }

    /* Null-move pruning. */
    if (!inCheck && depth >= 3 && hasNonPawnMaterial(e)) {
        int R = (depth >= 8) ? 3 : 2;
        BBCoreUndo u;
        int32_t score;
        bbCoreMakeNull(&e->core, &u);
        score = -negamax(e, depth - 1 - R, -beta, -beta + 1, ply + 1);
        bbCoreUnmakeNull(&e->core, &u);
        if (__atomic_load_n(&e->stop, __ATOMIC_RELAXED)) {
            return 0;
        }
        if (score >= beta) {
            return beta;
        }
    }

    n = bbGenPseudo(&e->core, moves);
    sortMoves(moves, n, ttMove, ply, e);

    best = -BB_INF;
    {
        int32_t alpha2 = alpha;
        for (i = 0; i < n; i++) {
            BBCoreUndo u;
            int32_t score;
            int moverColor = e->core.stm;
            bbCoreMake(&e->core, moves[i], &u);
            if (bbInCheckSide(&e->core, moverColor)) {
                bbCoreUnmake(&e->core, &u);
                continue;
            }
            moveCount++;
            if (moveCount == 1) {
                score = -negamax(e, depth - 1, -beta, -alpha2, ply + 1);
            } else {
                score = -negamax(e, depth - 1, -alpha2 - 1, -alpha2, ply + 1);
                if (score > alpha2 && score < beta) {
                    score = -negamax(e, depth - 1, -beta, -alpha2, ply + 1);
                }
            }
            bbCoreUnmake(&e->core, &u);
            if (__atomic_load_n(&e->stop, __ATOMIC_RELAXED)) {
                return 0;
            }
            if (score > best) {
                best = score;
                bestMove = moves[i];
                if (score > alpha2) {
                    alpha2 = score;
                    if (!bbMoveIsCapture(moves[i]) && ply < BB_PLY_MAX &&
                        moves[i] != e->killers[ply][0]) {
                        e->killers[ply][1] = e->killers[ply][0];
                        e->killers[ply][0] = moves[i];
                    }
                }
                if (alpha2 >= beta) {
                    break;
                }
            }
        }
    }

    if (moveCount == 0) {
        return inCheck ? -(BB_MATE - ply) : 0;
    }

    {
        int flags;
        if (best <= alpha) {
            flags = BB_TT_UPPER;
        } else if (best >= beta) {
            flags = BB_TT_LOWER;
        } else {
            flags = BB_TT_EXACT;
        }
        if (depth <= 255) {
            ttStore(&e->tt, e->core.key, bestMove, depth, flags, best);
        }
    }
    return best;
}

/* ------------------------------------------------------------------ */
/* PV extraction (follow TT best moves)                               */
/* ------------------------------------------------------------------ */

static int buildPv(struct BBEngine *e, BBMove *pv, int maxLen)
{
    int len = 0;
    int count = 0;
    BBCoreUndo undos[128];
    while (len < maxLen && len < 127) {
        uint16_t mv = ttProbeMove(&e->tt, e->core.key);
        BBCoreUndo u;
        int legal = 0;
        if (mv == 0) {
            break;
        }
        {
            int moverColor = e->core.stm;
            bbCoreMake(&e->core, (BBMove)mv, &u);
            legal = !bbInCheckSide(&e->core, moverColor);
        }
        if (!legal) {
            bbCoreUnmake(&e->core, &u);
            break;
        }
        if (bbIsRepetition(&e->core) || bbIsFiftyMove(&e->core)) {
            bbCoreUnmake(&e->core, &u);
            break;
        }
        undos[len] = u;
        pv[len] = (BBMove)mv;
        len++;
    }
    count = len;
    while (count > 0) {
        bbCoreUnmake(&e->core, &undos[count - 1]);
        count--;
    }
    return len;
}

/* ------------------------------------------------------------------ */
/* Iterative deepening                                                */
/* ------------------------------------------------------------------ */

static void printScore(int32_t score, char *out, size_t size)
{
    if (score > BB_MATE - 100) {
        int mateIn = (BB_MATE - (int)score + 1) / 2;
        (void)snprintf(out, size, "score mate %d", mateIn);
    } else if (score < -(BB_MATE - 100)) {
        int mateIn = (BB_MATE + (int)score + 1) / 2;
        (void)snprintf(out, size, "score mate -%d", mateIn);
    } else {
        (void)snprintf(out, size, "score cp %d", (int)score);
    }
}

static void reportInfo(const struct BBEngine *e, int depth, int32_t score,
                       const BBMove *pv, int pvLen)
{
    char scoreBuf[32];
    char pvBuf[1024] = {0};
    int64_t elapsed = nowMs() - e->startMs;
    int64_t nps = 0;
    size_t pos = 0;
    int i;
    if (elapsed > 0 && e->nodes > 0) {
        nps = e->nodes * 1000 / elapsed;
    }
    printScore(score, scoreBuf, sizeof(scoreBuf));
    for (i = 0; i < pvLen && pos + 8 < sizeof(pvBuf); i++) {
        char m[8];
        bbMoveToUci(pv[i], m, sizeof(m));
        pos += (size_t)snprintf(pvBuf + pos, sizeof(pvBuf) - pos, "%s%s",
                                i == 0 ? "" : " ", m);
    }
    printf("info depth %d %s nodes %lld time %lld nps %lld pv %s\n",
           depth, scoreBuf, (long long)e->nodes, (long long)elapsed,
           (long long)nps, pvBuf);
    (void)fflush(stdout);
}

static void iterativeDeepen(struct BBEngine *e)
{
    int depth;
    e->rootCount = bbGenLegal(&e->core, e->rootMoveList);
    e->rootBest = 0;
    e->lastScore = 0;

    for (depth = 1; depth <= e->depthLimit; depth++) {
        int i;
        int32_t alpha = -BB_INF;
        uint16_t sortedBest = 0;
        if (__atomic_load_n(&e->stop, __ATOMIC_RELAXED)) {
            break;
        }
        for (i = 0; i < e->rootCount; i++) {
            BBCoreUndo u;
            int32_t score;
            int moverColor = e->core.stm;
            bbCoreMake(&e->core, e->rootMoveList[i], &u);
            if (bbInCheckSide(&e->core, moverColor)) {
                bbCoreUnmake(&e->core, &u);
                continue;
            }
            score = -negamax(e, depth - 1, -BB_INF, -alpha, 1);
            bbCoreUnmake(&e->core, &u);
            if (__atomic_load_n(&e->stop, __ATOMIC_RELAXED)) {
                break;
            }
            if (score > alpha) {
                alpha = score;
                sortedBest = e->rootMoveList[i];
            }
        }
        if (__atomic_load_n(&e->stop, __ATOMIC_RELAXED)) {
            break;
        }
        if (sortedBest != 0) {
            e->rootBest = sortedBest;
            e->lastScore = alpha;
            ttStore(&e->tt, e->core.key, sortedBest, depth, BB_TT_LOWER, alpha);
        } else if (e->rootCount > 0) {
            e->rootBest = e->rootMoveList[0];
            e->lastScore = 0;
        }
        if (!e->quiet) {
            BBMove pv[128];
            int pvLen = buildPv(e, pv, 128);
            reportInfo(e, depth, e->lastScore, pv, pvLen);
        }
        if (e->softDeadline >= 0 && nowMs() >= e->softDeadline) {
            break;
        }
    }

    e->searchDone = 1;
    if (!e->quiet) {
        char m[8];
        if (e->rootBest != 0) {
            bbMoveToUci((BBMove)e->rootBest, m, sizeof(m));
        } else {
            (void)snprintf(m, sizeof(m), "0000");
        }
        (void)printf("bestmove %s\n", m);
        (void)fflush(stdout);
    }
}

/* ------------------------------------------------------------------ */
/* BBSearcher (Objective-C driver)                                    */
/* ------------------------------------------------------------------ */

@implementation BBSearcher

- (id)init
{
    return [self initWithHashBits:BB_TT_DEF_BITS];
}

- (id)initWithHashBits:(int)bits
{
    self = [super init];
    if (self != nil) {
        _engine = (struct BBEngine *)calloc(1, sizeof(struct BBEngine));
        if (_engine == NULL) {
            return nil;
        }
        __atomic_store_n(&_engine->stop, 0, __ATOMIC_RELAXED);
        bbCoreInit(&_engine->core, NULL);
        ttInit(&_engine->tt, bits);
        _engine->depthLimit = 128;
        _engine->moveTimeMs = -1;
        _engine->ourTimeMs = -1;
        _engine->incMs = 0;
        _engine->nodeLimit = 0;
        _engine->softDeadline = -1;
        _engine->hardDeadline = -1;
        _engine->bestUci[0] = '\0';
    }
    return self;
}

- (void)setPosition:(const BBCore *)pos
{
    bbCoreCopy(&_engine->core, pos);
}

- (void)setDepthLimit:(int)depth
{
    _engine->depthLimit = depth;
}

- (void)setMoveTimeMs:(int64_t)ms
{
    _engine->moveTimeMs = ms;
}

- (void)setClockTimeMs:(int64_t)ourTime incMs:(int64_t)inc
{
    _engine->ourTimeMs = ourTime;
    _engine->incMs = inc;
}

- (void)setNodeLimit:(int64_t)limit
{
    _engine->nodeLimit = limit;
}

- (void)newGame
{
    ttNewGame(&_engine->tt);
    memset(_engine->killers, 0, sizeof(_engine->killers));
    __atomic_store_n(&_engine->stop, 0, __ATOMIC_RELAXED);
}

- (void)search
{
    int64_t soft = -1;
    int64_t hard = -1;
    __atomic_store_n(&_engine->stop, 0, __ATOMIC_RELAXED);
    _engine->nodes = 0;
    _engine->startMs = nowMs();
    _engine->quiet = 0;

    if (_engine->moveTimeMs > 0) {
        soft = _engine->moveTimeMs;
        hard = _engine->moveTimeMs + 50;
    } else if (_engine->ourTimeMs > 0) {
        soft = _engine->ourTimeMs / 25 + _engine->incMs * 3 / 4;
        if (soft < 20) {
            soft = 20;
        }
        if (soft > _engine->ourTimeMs / 10) {
            soft = _engine->ourTimeMs / 10;
        }
        hard = soft + soft / 2;
    }
    if (soft >= 0) {
        _engine->softDeadline = _engine->startMs + soft;
        if (hard < soft) {
            hard = soft;
        }
        _engine->hardDeadline = _engine->startMs + hard;
    } else {
        _engine->softDeadline = -1;
        _engine->hardDeadline = -1;
    }

    iterativeDeepen(_engine);
}

- (void)stopSearch
{
    __atomic_store_n(&_engine->stop, 1, __ATOMIC_RELAXED);
}

- (int32_t)scoreAtDepth:(int)depth
{
    __atomic_store_n(&_engine->stop, 0, __ATOMIC_RELAXED);
    _engine->nodes = 0;
    _engine->startMs = nowMs();
    _engine->depthLimit = depth;
    _engine->softDeadline = -1;
    _engine->hardDeadline = -1;
    _engine->moveTimeMs = -1;
    _engine->ourTimeMs = -1;
    _engine->quiet = 1;

    iterativeDeepen(_engine);
    return _engine->lastScore;
}

- (int)bestMoveInto:(char *)buf size:(size_t)size
{
    if (size < 8 || _engine->rootBest == 0) {
        return -1;
    }
    bbMoveToUci((BBMove)_engine->rootBest, buf, size);
    return 0;
}

- (int64_t)nodesSearched
{
    return _engine->nodes;
}

@end