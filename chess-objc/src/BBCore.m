/* BBCore.m — C core implementation: position handling, Zobrist hashing,
 * move generation (with perft validation), castling, en passant, FEN I/O,
 * repetition / 50-move / insufficient-material rules, and a small attack-
 * counting helper used by the evaluator.
 */
#include "BBCore.h"

#include <pthread.h>
#include <stdio.h>
#include <string.h>

/* ------------------------------------------------------------------ */
/* Zobrist tables and the PRNG feeding them                            */
/* ------------------------------------------------------------------ */

static uint64_t gPieceKeys[12][64];
static uint64_t gSideKey;
static uint64_t gCastleKeys[16];
static uint64_t gEpKeys[8];
static pthread_once_t gZobristOnce = PTHREAD_ONCE_INIT;

static uint64_t gPrngState;

/* 0..11 slot into gPieceKeys: white 0..5, black 6..11, by piece type. */
static inline int pieceKeyIndex(BBPiece piece)
{
    return bbColorIndex(bbColorOf(piece)) * 6 + bbTypeOf(piece) - 1;
}

static void prngSeed(uint64_t seed)
{
    gPrngState = (seed != 0) ? seed : 0x9E3779B97F4A7C15ULL;
}

static uint64_t prngNext(void)
{
    uint64_t x = gPrngState;
    x ^= x >> 12;
    x ^= x << 25;
    x ^= x >> 27;
    gPrngState = x;
    return x * 0x2545F4914F6CDD1DULL;
}

static void buildZobrist(void)
{
    int color;
    int type;
    int sq;
    prngSeed(0);
    for (color = 0; color < 2; color++) {
        for (type = 1; type <= BB_KING; type++) {
            BBPiece piece = (BBPiece)((color == 0) ? (BB_WHITE | type) : (BB_BLACK | type));
            for (sq = 0; sq < 64; sq++) {
                gPieceKeys[pieceKeyIndex(piece)][sq] = prngNext();
            }
        }
    }
    gSideKey = prngNext();
    for (sq = 0; sq < 16; sq++) {
        gCastleKeys[sq] = prngNext();
    }
    for (sq = 0; sq < 8; sq++) {
        gEpKeys[sq] = prngNext();
    }
}

void bbZobristInit(void)
{
    pthread_once(&gZobristOnce, buildZobrist);
}

void bbZobristSetSeed(uint64_t seed)
{
    bbZobristInit();
    prngSeed(seed);
}

/* ------------------------------------------------------------------ */
/* Attack lookup tables                                               */
/* ------------------------------------------------------------------ */

static uint64_t gKnightAttacks[64];
static uint64_t gKingAttacks[64];

static const int8_t gKnightDelta[8][2] = {
    { 1, 2 }, { 2, 1 }, { 2, -1 }, { 1, -2 },
    { -1, -2 }, { -2, -1 }, { -2, 1 }, { -1, 2 }
};

static const int8_t gKingDelta[8][2] = {
    { 0, 1 }, { 1, 1 }, { 1, 0 }, { 1, -1 },
    { 0, -1 }, { -1, -1 }, { -1, 0 }, { -1, 1 }
};

static const int8_t gSlidingDelta[8][2] = {
    { 0, 1 }, { 1, 1 }, { 1, 0 }, { 1, -1 },
    { 0, -1 }, { -1, -1 }, { -1, 0 }, { -1, 1 }
};

static void buildAttackTables(void)
{
    int sq;
    int d;
    for (sq = 0; sq < 64; sq++) {
        int file = bbFileOf((BBSquare)sq);
        int rank = bbRankOf((BBSquare)sq);
        uint64_t knight = 0;
        uint64_t king = 0;
        for (d = 0; d < 8; d++) {
            int nf = file + gKnightDelta[d][0];
            int nr = rank + gKnightDelta[d][1];
            if (nf >= 0 && nf < 8 && nr >= 0 && nr < 8) {
                knight |= 1ULL << bbSquare(nf, nr);
            }
            int kf = file + gKingDelta[d][0];
            int kr = rank + gKingDelta[d][1];
            if (kf >= 0 && kf < 8 && kr >= 0 && kr < 8) {
                king |= 1ULL << bbSquare(kf, kr);
            }
        }
        gKnightAttacks[sq] = knight;
        gKingAttacks[sq] = king;
    }
}

void bbCoreInit(BBCore *b, const char *fen)
{
    int i;
    bbZobristInit();
    if (gKnightAttacks[0] == 0 && gKingAttacks[0] == 0) {
        buildAttackTables();
    }

    memset(b, 0, sizeof(*b));
    for (i = 0; i < 64; i++) {
        b->squares[i] = BB_EMPTY;
    }
    b->stm = BB_WHITE;
    b->castle = 0;
    b->ep = -1;
    b->kingPos[bbColorIndex(BB_WHITE)] = -1;
    b->kingPos[bbColorIndex(BB_BLACK)] = -1;

    if (fen == NULL || fen[0] == '\0') {
        bbCoreInit(b, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
        return;
    }

    {
        const char *p = fen;
        int sq = 56; /* a8 */
        while (*p != '\0' && *p != ' ') {
            char c = *p;
            if (c == '/') {
                sq -= 16;
            } else if (c >= '1' && c <= '8') {
                sq += (int)(c - '0');
            } else {
                static const char *wPieces = "PNBRQK";
                static const char *bPieces = "pnbrqk";
                const char *w = strchr(wPieces, c);
                const char *bl = (w == NULL) ? strchr(bPieces, c) : NULL;
                int type = 0;
                if (w != NULL) {
                    type = (int)(w - wPieces) + 1;
                } else if (bl != NULL) {
                    type = (int)(bl - bPieces) + 1;
                } else {
                    break;
                }
                if (sq >= 0 && sq < 64 && c != '\0') {
                    if (w != NULL) {
                        b->squares[sq] = (BBPiece)(BB_WHITE | type);
                    } else {
                        b->squares[sq] = (BBPiece)(BB_BLACK | type);
                    }
                }
                sq++;
            }
            p++;
        }
        while (*p == ' ') {
            p++;
        }
        if (*p == 'w') {
            b->stm = BB_WHITE;
        } else if (*p == 'b') {
            b->stm = BB_BLACK;
        }
        while (*p != '\0' && *p != ' ') {
            p++;
        }
        while (*p == ' ') {
            p++;
        }
        /* Castling rights: consume the whole token (e.g. "KQkq", "-"). */
        b->castle = 0;
        while (*p != '\0' && *p != ' ') {
            switch (*p) {
            case 'K':
                b->castle |= BB_CASTLE_WK;
                break;
            case 'Q':
                b->castle |= BB_CASTLE_WQ;
                break;
            case 'k':
                b->castle |= BB_CASTLE_BK;
                break;
            case 'q':
                b->castle |= BB_CASTLE_BQ;
                break;
            default:
                break;
            }
            p++;
        }
        while (*p == ' ') {
            p++;
        }
        if (*p == '-') {
            b->ep = -1;
        } else if (*p >= 'a' && *p <= 'h' && *(p + 1) >= '1' && *(p + 1) <= '8') {
            b->ep = bbSquare((int)(*p - 'a'), (int)(*(p + 1) - '1'));
        }
        while (*p != '\0' && *p != ' ') {
            p++;
        }
        while (*p == ' ') {
            p++;
        }
        b->halfmove = 0;
        b->fullmove = 1;
        if (*p >= '0' && *p <= '9') {
            b->halfmove = (int32_t)(b->halfmove * 10 + (*p - '0'));
            p++;
            while (*p >= '0' && *p <= '9') {
                b->halfmove = (int32_t)(b->halfmove * 10 + (*p - '0'));
                p++;
            }
        }
        while (*p == ' ') {
            p++;
        }
        if (*p >= '0' && *p <= '9') {
            b->fullmove = 0;
            while (*p >= '0' && *p <= '9') {
                b->fullmove = (int32_t)(b->fullmove * 10 + (*p - '0'));
                p++;
            }
        }
    }

    b->key = 0;
    for (i = 0; i < 64; i++) {
        BBPiece pc = b->squares[i];
        if (pc != BB_EMPTY) {
            b->key ^= gPieceKeys[pieceKeyIndex(pc)][i];
            if (bbTypeOf(pc) == BB_KING) {
                b->kingPos[bbColorIndex(bbColorOf(pc))] = (BBSquare)i;
            }
        }
    }
    if (b->stm == BB_BLACK) {
        b->key ^= gSideKey;
    }
    b->key ^= gCastleKeys[b->castle & 0x0f];
    if (b->ep >= 0) {
        b->key ^= gEpKeys[bbFileOf(b->ep)];
    }
    b->keys[0] = b->key;
    b->keyCount = 1;
}

void bbCoreCopy(BBCore *dst, const BBCore *src)
{
    *dst = *src;
}

/* ------------------------------------------------------------------ */
/* Attack predicate + helpers                                         */
/* ------------------------------------------------------------------ */

int bbSquareAttacked(const BBCore *b, BBSquare sq, int byColor)
{
    int file = bbFileOf(sq);
    int rank = bbRankOf(sq);

    /* Pawn attacks: for a white attacker, the pawn sits one rank below the
     * target on a neighbouring file; mirrored for black. */
    if (byColor == BB_WHITE) {
        if (rank > 0) {
            if (file > 0 && b->squares[sq - 9] == (BBPiece)(BB_WHITE | BB_PAWN)) {
                return 1;
            }
            if (file < 7 && b->squares[sq - 7] == (BBPiece)(BB_WHITE | BB_PAWN)) {
                return 1;
            }
        }
    } else {
        if (rank < 7) {
            if (file > 0 && b->squares[sq + 7] == (BBPiece)(BB_BLACK | BB_PAWN)) {
                return 1;
            }
            if (file < 7 && b->squares[sq + 9] == (BBPiece)(BB_BLACK | BB_PAWN)) {
                return 1;
            }
        }
    }

    {
        uint64_t mask = gKnightAttacks[sq];
        if (mask != 0) {
            int d;
            for (d = 0; d < 8; d++) {
                int nf = file + gKnightDelta[d][0];
                int nr = rank + gKnightDelta[d][1];
                if (nf >= 0 && nf < 8 && nr >= 0 && nr < 8 &&
                    b->squares[bbSquare(nf, nr)] == (BBPiece)(byColor | BB_KNIGHT)) {
                    return 1;
                }
            }
        }
        mask = gKingAttacks[sq];
        if (mask != 0) {
            int d;
            for (d = 0; d < 8; d++) {
                int kf = file + gKingDelta[d][0];
                int kr = rank + gKingDelta[d][1];
                if (kf >= 0 && kf < 8 && kr >= 0 && kr < 8 &&
                    b->squares[bbSquare(kf, kr)] == (BBPiece)(byColor | BB_KING)) {
                    return 1;
                }
            }
        }
    }

    /* Sliding pieces. */
    {
        int d;
        for (d = 0; d < 8; d++) {
            int f = file + gSlidingDelta[d][0];
            int r = rank + gSlidingDelta[d][1];
            while (f >= 0 && f < 8 && r >= 0 && r < 8) {
                BBPiece pc = b->squares[bbSquare(f, r)];
                if (pc != BB_EMPTY) {
                    int type = bbTypeOf(pc);
                    int isOrtho = (d % 2 == 0);
                    if (bbColorOf(pc) == byColor) {
                        if (isOrtho && (type == BB_ROOK || type == BB_QUEEN)) {
                            return 1;
                        }
                        if (!isOrtho && (type == BB_BISHOP || type == BB_QUEEN)) {
                            return 1;
                        }
                    }
                    break;
                }
                f += gSlidingDelta[d][0];
                r += gSlidingDelta[d][1];
            }
        }
    }
    return 0;
}

int bbInCheckSide(const BBCore *b, int color)
{
    int other = (color == BB_WHITE) ? BB_BLACK : BB_WHITE;
    BBSquare ksq = b->kingPos[bbColorIndex(color)];
    if (ksq < 0) {
        return 0;
    }
    return bbSquareAttacked(b, ksq, other);
}

int bbInCheck(const BBCore *b)
{
    return bbInCheckSide(b, b->stm);
}

int bbLitMoves(const BBCore *b, BBSquare from, BBPiece piece)
{
    int ownColor = bbColorOf(piece);
    int type = bbTypeOf(piece);
    int file = bbFileOf(from);
    int rank = bbRankOf(from);
    int count = 0;
    int d;

    if (type == BB_PAWN) {
        int dir = (ownColor == BB_WHITE) ? 1 : -1;
        if (file > 0) {
            int nf = file - 1;
            int nr = rank + dir;
            if (nr >= 0 && nr < 8) {
                BBPiece pc = b->squares[bbSquare(nf, nr)];
                if (pc == BB_EMPTY || bbColorOf(pc) != ownColor) {
                    count++;
                }
            }
        }
        if (file < 7) {
            int nf = file + 1;
            int nr = rank + dir;
            if (nr >= 0 && nr < 8) {
                BBPiece pc = b->squares[bbSquare(nf, nr)];
                if (pc == BB_EMPTY || bbColorOf(pc) != ownColor) {
                    count++;
                }
            }
        }
        return count;
    }

    if (type == BB_KNIGHT || type == BB_KING) {
        for (d = 0; d < 8; d++) {
            int nf;
            int nr;
            if (type == BB_KNIGHT) {
                nf = file + gKnightDelta[d][0];
                nr = rank + gKnightDelta[d][1];
            } else {
                nf = file + gKingDelta[d][0];
                nr = rank + gKingDelta[d][1];
            }
            if (nf >= 0 && nf < 8 && nr >= 0 && nr < 8) {
                BBPiece pc = b->squares[bbSquare(nf, nr)];
                if (pc == BB_EMPTY || bbColorOf(pc) != ownColor) {
                    count++;
                }
            }
        }
        return count;
    }

    for (d = 0; d < 8; d++) {
        int isOrtho = (d % 2 == 0);
        if ((type == BB_BISHOP && isOrtho) || (type == BB_ROOK && !isOrtho)) {
            continue;
        }
        {
            int f = file + gSlidingDelta[d][0];
            int r = rank + gSlidingDelta[d][1];
            while (f >= 0 && f < 8 && r >= 0 && r < 8) {
                BBPiece pc = b->squares[bbSquare(f, r)];
                if (pc == BB_EMPTY) {
                    count++;
                } else {
                    if (bbColorOf(pc) != ownColor) {
                        count++;
                    }
                    break;
                }
                f += gSlidingDelta[d][0];
                r += gSlidingDelta[d][1];
            }
        }
    }
    return count;
}

/* ------------------------------------------------------------------ */
/* Move generation                                                    */
/* ------------------------------------------------------------------ */

static int pawnMoves(const BBCore *b, BBMove *out, BBSquare from)
{
    int file = bbFileOf(from);
    int rank = bbRankOf(from);
    int dir = (b->stm == BB_WHITE) ? 1 : -1;
    int promoRank = (b->stm == BB_WHITE) ? 6 : 1;
    int count = 0;
    int firstRank = (b->stm == BB_WHITE) ? 1 : 6;
    int nf;
    int nr;
    int promo;

    nr = rank + dir;
    if (nr >= 0 && nr < 8) {
        nf = file;
        if (b->squares[bbSquare(nf, nr)] == BB_EMPTY) {
            if (rank == promoRank) {
                for (promo = 0; promo < 4; promo++) {
                    out[count++] = bbMakeMove(from, bbSquare(nf, nr), BB_MOVE_PROMO_Q + promo);
                }
            } else {
                out[count++] = bbMakeMove(from, bbSquare(nf, nr), BB_MOVE_QUIET);
            }
            if (rank == firstRank) {
                BBSquare two = bbSquare(nf, nr + dir);
                if (nr + dir >= 0 && nr + dir < 8 && b->squares[two] == BB_EMPTY) {
                    out[count++] = bbMakeMove(from, two, BB_MOVE_DPAWN);
                }
            }
        }
    }

    for (nf = file - 1; nf <= file + 1; nf += 2) {
        if (nf < 0 || nf > 7) {
            continue;
        }
        nr = rank + dir;
        if (nr < 0 || nr >= 8) {
            continue;
        }
        {
            BBSquare to = bbSquare(nf, nr);
            BBPiece pc = b->squares[to];
            if (pc != BB_EMPTY && bbColorOf(pc) != b->stm) {
                if (rank == promoRank) {
                    for (promo = 0; promo < 4; promo++) {
                        out[count++] = bbMakeMove(from, to, BB_MOVE_PROMO_CAP_Q + promo);
                    }
                } else {
                    out[count++] = bbMakeMove(from, to, BB_MOVE_CAPTURE);
                }
            } else if (to == b->ep) {
                out[count++] = bbMakeMove(from, to, BB_MOVE_EP);
            }
        }
    }
    return count;
}

static int knightMoves(const BBCore *b, BBMove *out, BBSquare from)
{
    int file = bbFileOf(from);
    int rank = bbRankOf(from);
    int count = 0;
    int d;
    for (d = 0; d < 8; d++) {
        int nf = file + gKnightDelta[d][0];
        int nr = rank + gKnightDelta[d][1];
        if (nf >= 0 && nf < 8 && nr >= 0 && nr < 8) {
            BBSquare to = bbSquare(nf, nr);
            BBPiece pc = b->squares[to];
            if (pc == BB_EMPTY) {
                out[count++] = bbMakeMove(from, to, BB_MOVE_QUIET);
            } else if (bbColorOf(pc) != b->stm) {
                out[count++] = bbMakeMove(from, to, BB_MOVE_CAPTURE);
            }
        }
    }
    return count;
}

static int kingMoves(const BBCore *b, BBMove *out, BBSquare from)
{
    int file = bbFileOf(from);
    int rank = bbRankOf(from);
    int count = 0;
    int d;
    int other = (b->stm == BB_WHITE) ? BB_BLACK : BB_WHITE;
    for (d = 0; d < 8; d++) {
        int nf = file + gKingDelta[d][0];
        int nr = rank + gKingDelta[d][1];
        if (nf >= 0 && nf < 8 && nr >= 0 && nr < 8) {
            BBSquare to = bbSquare(nf, nr);
            BBPiece pc = b->squares[to];
            if (pc == BB_EMPTY) {
                out[count++] = bbMakeMove(from, to, BB_MOVE_QUIET);
            } else if (bbColorOf(pc) != b->stm) {
                out[count++] = bbMakeMove(from, to, BB_MOVE_CAPTURE);
            }
        }
    }

    /* Castling. */
    if (b->castle != 0) {
        int e1 = bbSquare(4, 0);
        int e8 = bbSquare(4, 7);
        BBSquare ksq = (b->stm == BB_WHITE) ? (BBSquare)e1 : (BBSquare)e8;
        BBPiece king = (BBPiece)(b->stm | BB_KING);
        if (from == ksq && b->squares[ksq] == king && !bbSquareAttacked(b, ksq, other)) {
            int h1 = bbSquare(7, 0);
            int h8 = bbSquare(7, 7);
            int a1 = bbSquare(0, 0);
            int a8 = bbSquare(0, 7);
            BBPiece rook = (BBPiece)(b->stm | BB_ROOK);
            if (b->stm == BB_WHITE) {
                if ((b->castle & BB_CASTLE_WK) != 0 &&
                    b->squares[h1] == rook &&
                    b->squares[bbSquare(5, 0)] == BB_EMPTY &&
                    b->squares[bbSquare(6, 0)] == BB_EMPTY &&
                    !bbSquareAttacked(b, bbSquare(5, 0), other) &&
                    !bbSquareAttacked(b, bbSquare(6, 0), other)) {
                    out[count++] = bbMakeMove(ksq, bbSquare(6, 0), BB_MOVE_CASTLE_K);
                }
                if ((b->castle & BB_CASTLE_WQ) != 0 &&
                    b->squares[a1] == rook &&
                    b->squares[bbSquare(1, 0)] == BB_EMPTY &&
                    b->squares[bbSquare(2, 0)] == BB_EMPTY &&
                    b->squares[bbSquare(3, 0)] == BB_EMPTY &&
                    !bbSquareAttacked(b, bbSquare(2, 0), other) &&
                    !bbSquareAttacked(b, bbSquare(3, 0), other)) {
                    out[count++] = bbMakeMove(ksq, bbSquare(2, 0), BB_MOVE_CASTLE_Q);
                }
            } else {
                if ((b->castle & BB_CASTLE_BK) != 0 &&
                    b->squares[h8] == rook &&
                    b->squares[bbSquare(5, 7)] == BB_EMPTY &&
                    b->squares[bbSquare(6, 7)] == BB_EMPTY &&
                    !bbSquareAttacked(b, bbSquare(5, 7), other) &&
                    !bbSquareAttacked(b, bbSquare(6, 7), other)) {
                    out[count++] = bbMakeMove(ksq, bbSquare(6, 7), BB_MOVE_CASTLE_K);
                }
                if ((b->castle & BB_CASTLE_BQ) != 0 &&
                    b->squares[a8] == rook &&
                    b->squares[bbSquare(1, 7)] == BB_EMPTY &&
                    b->squares[bbSquare(2, 7)] == BB_EMPTY &&
                    b->squares[bbSquare(3, 7)] == BB_EMPTY &&
                    !bbSquareAttacked(b, bbSquare(2, 7), other) &&
                    !bbSquareAttacked(b, bbSquare(3, 7), other)) {
                    out[count++] = bbMakeMove(ksq, bbSquare(2, 7), BB_MOVE_CASTLE_Q);
                }
            }
        }
    }
    return count;
}

static int slidingMoves(const BBCore *b, BBMove *out, BBSquare from, BBPiece piece)
{
    int file = bbFileOf(from);
    int rank = bbRankOf(from);
    int type = bbTypeOf(piece);
    int count = 0;
    int d;
    for (d = 0; d < 8; d++) {
        int isOrtho = (d % 2 == 0);
        if ((type == BB_BISHOP && isOrtho) || (type == BB_ROOK && !isOrtho)) {
            continue;
        }
        {
            int f = file + gSlidingDelta[d][0];
            int r = rank + gSlidingDelta[d][1];
            while (f >= 0 && f < 8 && r >= 0 && r < 8) {
                BBSquare to = bbSquare(f, r);
                BBPiece pc = b->squares[to];
                if (pc == BB_EMPTY) {
                    out[count++] = bbMakeMove(from, to, BB_MOVE_QUIET);
                } else if (bbColorOf(pc) != b->stm) {
                    out[count++] = bbMakeMove(from, to, BB_MOVE_CAPTURE);
                    break;
                } else {
                    break;
                }
                f += gSlidingDelta[d][0];
                r += gSlidingDelta[d][1];
            }
        }
    }
    return count;
}

int bbGenPseudo(const BBCore *b, BBMove *out)
{
    int i;
    int count = 0;
    for (i = 0; i < 64; i++) {
        BBPiece pc = b->squares[i];
        if (pc == BB_EMPTY || bbColorOf(pc) != b->stm) {
            continue;
        }
        switch (bbTypeOf(pc)) {
        case BB_PAWN:
            count += pawnMoves(b, out + count, (BBSquare)i);
            break;
        case BB_KNIGHT:
            count += knightMoves(b, out + count, (BBSquare)i);
            break;
        case BB_KING:
            count += kingMoves(b, out + count, (BBSquare)i);
            break;
        default:
            count += slidingMoves(b, out + count, (BBSquare)i, pc);
            break;
        }
    }
    return count;
}

int bbGenLegal(const BBCore *b, BBMove *out)
{
    BBMove pseudo[256];
    int n = bbGenPseudo(b, pseudo);
    int count = 0;
    int i;
    for (i = 0; i < n; i++) {
        BBCore copy = *b;
        BBCoreUndo u;
        int moverColor = bbColorOf(b->squares[bbMoveFrom(pseudo[i])]);
        bbCoreMake(&copy, pseudo[i], &u);
        if (!bbInCheckSide(&copy, moverColor)) {
            out[count++] = pseudo[i];
        }
    }
    return count;
}

int bbHasLegal(const BBCore *b)
{
    BBMove moves[256];
    return bbGenLegal(b, moves) > 0;
}

/* ------------------------------------------------------------------ */
/* make / unmake                                                      */
/* ------------------------------------------------------------------ */

void bbCoreMake(BBCore *b, BBMove move, BBCoreUndo *undo)
{
    BBSquare from = bbMoveFrom(move);
    BBSquare to = bbMoveTo(move);
    int flags = bbMoveFlags(move);
    BBPiece mover = b->squares[from];
    int moverColor = bbColorOf(mover);
    BBPiece captured = b->squares[to];
    BBSquare epPawn = -1;
    int prevCastle = b->castle;
    int newCastle = b->castle;
    int isPawnMove = (bbTypeOf(mover) == BB_PAWN);
    int isCapture = bbMoveIsCapture(move);

    undo->move = move;
    undo->prevCastle = prevCastle;
    undo->prevEp = b->ep;
    undo->prevHalfmove = b->halfmove;
    undo->prevKey = b->key;
    undo->prevKeyCount = b->keyCount;

    if (flags == BB_MOVE_EP) {
        epPawn = (moverColor == BB_WHITE) ? (BBSquare)(to - 8) : (BBSquare)(to + 8);
        captured = b->squares[epPawn];
    }
    undo->captured = captured;

    /* Remove mover + captured from the hash. */
    b->key ^= gPieceKeys[pieceKeyIndex(mover)][from];
    if (captured != BB_EMPTY) {
        if (flags == BB_MOVE_EP) {
            b->key ^= gPieceKeys[pieceKeyIndex(captured)][epPawn];
            b->squares[epPawn] = BB_EMPTY;
        } else {
            b->key ^= gPieceKeys[pieceKeyIndex(captured)][to];
        }
    }

    b->squares[from] = BB_EMPTY;
    b->squares[to] = mover;
    b->key ^= gPieceKeys[pieceKeyIndex(mover)][to];
    if (bbTypeOf(mover) == BB_KING) {
        b->kingPos[bbColorIndex(moverColor)] = to;
    }

    if (flags == BB_MOVE_CASTLE_K || flags == BB_MOVE_CASTLE_Q) {
        BBSquare rookFrom;
        BBSquare rookTo;
        int rookFromSq;
        int rookToSq;
        BBPiece rook = (BBPiece)(moverColor | BB_ROOK);
        if (moverColor == BB_WHITE) {
            rookFrom = flags == BB_MOVE_CASTLE_K ? bbSquare(7, 0) : bbSquare(0, 0);
            rookTo = flags == BB_MOVE_CASTLE_K ? bbSquare(5, 0) : bbSquare(3, 0);
        } else {
            rookFrom = flags == BB_MOVE_CASTLE_K ? bbSquare(7, 7) : bbSquare(0, 7);
            rookTo = flags == BB_MOVE_CASTLE_K ? bbSquare(5, 7) : bbSquare(3, 7);
        }
        rookFromSq = rookFrom;
        rookToSq = rookTo;
        b->key ^= gPieceKeys[pieceKeyIndex(rook)][rookFromSq];
        b->squares[rookFromSq] = BB_EMPTY;
        b->squares[rookToSq] = rook;
        b->key ^= gPieceKeys[pieceKeyIndex(rook)][rookToSq];
    } else if (flags == BB_MOVE_PROMO_Q || flags == BB_MOVE_PROMO_R ||
               flags == BB_MOVE_PROMO_B || flags == BB_MOVE_PROMO_N ||
               flags == BB_MOVE_PROMO_CAP_Q || flags == BB_MOVE_PROMO_CAP_R ||
               flags == BB_MOVE_PROMO_CAP_B || flags == BB_MOVE_PROMO_CAP_N) {
        int promoBase = (flags >= BB_MOVE_PROMO_CAP_Q) ? BB_MOVE_PROMO_CAP_Q
                                                       : BB_MOVE_PROMO_Q;
        int promoType = BB_QUEEN - (flags - promoBase);
        BBPiece promo = (BBPiece)(moverColor | promoType);
        b->key ^= gPieceKeys[pieceKeyIndex(mover)][to];
        b->squares[to] = promo;
        b->key ^= gPieceKeys[pieceKeyIndex(promo)][to];
    }

    /* Update castling rights. */
    if ((prevCastle & (BB_CASTLE_WK | BB_CASTLE_WQ)) != 0) {
        if (from == 4 || to == 4) {
            newCastle &= ~(BB_CASTLE_WK | BB_CASTLE_WQ);
        } else {
            if (from == 0 || to == 0) {
                newCastle &= ~BB_CASTLE_WQ;
            }
            if (from == 7 || to == 7) {
                newCastle &= ~BB_CASTLE_WK;
            }
        }
    }
    if ((prevCastle & (BB_CASTLE_BK | BB_CASTLE_BQ)) != 0) {
        if (from == 60 || to == 60) {
            newCastle &= ~(BB_CASTLE_BK | BB_CASTLE_BQ);
        } else {
            if (from == 56 || to == 56) {
                newCastle &= ~BB_CASTLE_BQ;
            }
            if (from == 63 || to == 63) {
                newCastle &= ~BB_CASTLE_BK;
            }
        }
    }
    if (newCastle != prevCastle) {
        b->key ^= gCastleKeys[prevCastle & 0x0f];
        b->key ^= gCastleKeys[newCastle & 0x0f];
        b->castle = newCastle;
    }

    /* En passant square. */
    if ((flags == BB_MOVE_DPAWN) && (b->ep != from + ((moverColor == BB_WHITE) ? 8 : -8))) {
        if (b->ep >= 0) {
            b->key ^= gEpKeys[bbFileOf(b->ep)];
        }
        b->ep = (BBSquare)(from + ((moverColor == BB_WHITE) ? 8 : -8));
        b->key ^= gEpKeys[bbFileOf(b->ep)];
    } else {
        if (b->ep >= 0) {
            b->key ^= gEpKeys[bbFileOf(b->ep)];
        }
        b->ep = -1;
    }

    /* Halfmove clock. */
    if (isPawnMove || isCapture) {
        b->halfmove = 0;
    } else {
        b->halfmove++;
    }
    if (moverColor == BB_BLACK) {
        b->fullmove++;
    }

    /* Side to move. */
    b->stm = (b->stm == BB_WHITE) ? BB_BLACK : BB_WHITE;
    b->key ^= gSideKey;

    /* History. */
    if (b->keyCount < (int32_t)(sizeof(b->keys) / sizeof(b->keys[0]))) {
        b->keys[b->keyCount] = b->key;
        b->keyCount++;
    }
}

void bbCoreUnmake(BBCore *b, const BBCoreUndo *undo)
{
    BBMove move = undo->move;
    BBSquare from = bbMoveFrom(move);
    BBSquare to = bbMoveTo(move);
    int flags = bbMoveFlags(move);
    int moverColor = b->stm == BB_WHITE ? BB_BLACK : BB_WHITE;
    BBPiece movedPiece = b->squares[to];

    b->squares[from] = BB_EMPTY;
    b->squares[to] = BB_EMPTY;

    if (flags == BB_MOVE_CASTLE_K || flags == BB_MOVE_CASTLE_Q) {
        BBSquare rookFrom;
        BBSquare rookTo;
        BBPiece rook = (BBPiece)(moverColor | BB_ROOK);
        if (moverColor == BB_WHITE) {
            rookFrom = flags == BB_MOVE_CASTLE_K ? bbSquare(7, 0) : bbSquare(0, 0);
            rookTo = flags == BB_MOVE_CASTLE_K ? bbSquare(5, 0) : bbSquare(3, 0);
        } else {
            rookFrom = flags == BB_MOVE_CASTLE_K ? bbSquare(7, 7) : bbSquare(0, 7);
            rookTo = flags == BB_MOVE_CASTLE_K ? bbSquare(5, 7) : bbSquare(3, 7);
        }
        b->squares[rookTo] = BB_EMPTY;
        b->squares[rookFrom] = rook;
        b->squares[from] = (BBPiece)(moverColor | BB_KING);
    } else if (flags == BB_MOVE_PROMO_Q || flags == BB_MOVE_PROMO_R ||
               flags == BB_MOVE_PROMO_B || flags == BB_MOVE_PROMO_N ||
               flags == BB_MOVE_PROMO_CAP_Q || flags == BB_MOVE_PROMO_CAP_R ||
               flags == BB_MOVE_PROMO_CAP_B || flags == BB_MOVE_PROMO_CAP_N) {
        b->squares[from] = (BBPiece)(moverColor | BB_PAWN);
    } else {
        b->squares[from] = movedPiece;
    }

    if (flags == BB_MOVE_EP) {
        BBSquare epPawn = (moverColor == BB_WHITE) ? (BBSquare)(to - 8) : (BBSquare)(to + 8);
        b->squares[epPawn] = undo->captured;
    } else {
        b->squares[to] = undo->captured;
    }

    b->stm = (b->stm == BB_WHITE) ? BB_BLACK : BB_WHITE;
    b->castle = undo->prevCastle;
    b->ep = undo->prevEp;
    b->halfmove = undo->prevHalfmove;
    b->fullmove = (int32_t)(b->fullmove - (b->stm == BB_WHITE ? 1 : 0));
    if (b->stm == BB_BLACK) {
        b->fullmove--;
    }
    b->key = undo->prevKey;
    b->keyCount = undo->prevKeyCount;
    {
        BBPiece restored = b->squares[from];
        if (bbTypeOf(restored) == BB_KING) {
            b->kingPos[bbColorIndex(bbColorOf(restored))] = from;
        }
    }
}

void bbCoreMakeNull(BBCore *b, BBCoreUndo *undo)
{
    undo->move = 0;
    undo->captured = BB_EMPTY;
    undo->prevCastle = b->castle;
    undo->prevEp = b->ep;
    undo->prevHalfmove = b->halfmove;
    undo->prevKey = b->key;
    undo->prevKeyCount = b->keyCount;

    b->stm = (b->stm == BB_WHITE) ? BB_BLACK : BB_WHITE;
    b->key ^= gSideKey;
    b->halfmove++;
}

void bbCoreUnmakeNull(BBCore *b, const BBCoreUndo *undo)
{
    b->stm = (b->stm == BB_WHITE) ? BB_BLACK : BB_WHITE;
    b->key = undo->prevKey;
    b->halfmove = undo->prevHalfmove;
    b->keyCount = undo->prevKeyCount;
    b->ep = undo->prevEp;
    b->castle = undo->prevCastle;
}

/* ------------------------------------------------------------------ */
/* Rule predicates                                                   */
/* ------------------------------------------------------------------ */

int bbIsRepetition(const BBCore *b)
{
    int i;
    int matches = 0;
    int scanned = 0;
    for (i = b->keyCount - 1; i >= 0 && scanned < 100; i -= 2) {
        scanned++;
        if (b->keys[i] == b->key) {
            matches++;
            if (matches >= 3) {
                return 1;
            }
        }
    }
    return 0;
}

int bbIsFiftyMove(const BBCore *b)
{
    return b->halfmove >= 100;
}

int bbInsufficientMaterial(const BBCore *b)
{
    int i;
    int minorCount = 0;
    int bishopsParity = -1;
    for (i = 0; i < 64; i++) {
        BBPiece pc = b->squares[i];
        if (pc == BB_EMPTY) {
            continue;
        }
        switch (bbTypeOf(pc)) {
        case BB_PAWN:
        case BB_ROOK:
        case BB_QUEEN:
            return 0;
        case BB_KNIGHT:
            minorCount++;
            break;
        case BB_BISHOP:
            minorCount++;
            {
                int sqParity = (bbFileOf((BBSquare)i) + bbRankOf((BBSquare)i)) & 1;
                if (bishopsParity < 0) {
                    bishopsParity = sqParity;
                } else if (bishopsParity != sqParity) {
                    bishopsParity = 2;
                }
            }
            break;
        default:
            break;
        }
    }
    if (minorCount == 0) {
        return 1;
    }
    if (minorCount == 1) {
        return 1;
    }
    if (minorCount == 2) {
        if (bishopsParity == 0 || bishopsParity == 1) {
            return 1; /* K+B vs K+B with same-coloured bishops */
        }
        return 0;
    }
    return 0;
}

int bbIsCheckmate(const BBCore *b)
{
    return !bbHasLegal(b) && bbInCheck(b);
}

/* ------------------------------------------------------------------ */
/* Perft                                                              */
/* ------------------------------------------------------------------ */

int64_t bbPerft(BBCore *b, int depth)
{
    BBMove moves[256];
    int n = bbGenLegal(b, moves);
    int64_t sum = 0;
    BBCoreUndo u;
    int i;
    if (depth <= 0) {
        return 1;
    }
    if (depth == 1) {
        return (int64_t)n;
    }
    for (i = 0; i < n; i++) {
        bbCoreMake(b, moves[i], &u);
        sum += bbPerft(b, depth - 1);
        bbCoreUnmake(b, &u);
    }
    return sum;
}

/* ------------------------------------------------------------------ */
/* Serialisation                                                      */
/* ------------------------------------------------------------------ */

void bbMoveToUci(BBMove move, char *out, size_t outSize)
{
    BBSquare from = bbMoveFrom(move);
    BBSquare to = bbMoveTo(move);
    int flags = bbMoveFlags(move);
    if (outSize < 6) {
        return;
    }
    out[0] = (char)('a' + bbFileOf(from));
    out[1] = (char)('1' + bbRankOf(from));
    out[2] = (char)('a' + bbFileOf(to));
    out[3] = (char)('1' + bbRankOf(to));
    out[4] = '\0';
    if ((flags == BB_MOVE_PROMO_Q) || (flags == BB_MOVE_PROMO_CAP_Q)) {
        out[4] = 'q';
        out[5] = '\0';
    } else if ((flags == BB_MOVE_PROMO_R) || (flags == BB_MOVE_PROMO_CAP_R)) {
        out[4] = 'r';
        out[5] = '\0';
    } else if ((flags == BB_MOVE_PROMO_B) || (flags == BB_MOVE_PROMO_CAP_B)) {
        out[4] = 'b';
        out[5] = '\0';
    } else if ((flags == BB_MOVE_PROMO_N) || (flags == BB_MOVE_PROMO_CAP_N)) {
        out[4] = 'n';
        out[5] = '\0';
    }
}

void bbToFen(const BBCore *b, char *out, size_t outSize)
{
    int rank;
    int file;
    int empty = 0;
    size_t pos = 0;
    if (outSize == 0) {
        return;
    }
    for (rank = 7; rank >= 0; rank--) {
        for (file = 0; file < 8; file++) {
            BBPiece pc = b->squares[bbSquare(file, rank)];
            if (pc == BB_EMPTY) {
                empty++;
                continue;
            }
            if (empty > 0) {
                if (pos + 1 < outSize) {
                    out[pos++] = (char)('0' + empty);
                }
                empty = 0;
            }
            {
                char c = ' ';
                switch (bbTypeOf(pc)) {
                case BB_PAWN: c = 'p'; break;
                case BB_KNIGHT: c = 'n'; break;
                case BB_BISHOP: c = 'b'; break;
                case BB_ROOK: c = 'r'; break;
                case BB_QUEEN: c = 'q'; break;
                case BB_KING: c = 'k'; break;
                default: break;
                }
                if (bbColorOf(pc) == BB_WHITE) {
                    c = (char)(c - 32);
                }
                if (pos + 1 < outSize) {
                    out[pos++] = c;
                }
            }
        }
        if (empty > 0) {
            if (pos + 1 < outSize) {
                out[pos++] = (char)('0' + empty);
            }
            empty = 0;
        }
        if (rank > 0) {
            if (pos + 1 < outSize) {
                out[pos++] = '/';
            }
        }
    }
    {
        const char *side = (b->stm == BB_WHITE) ? " w " : " b ";
        size_t len = strlen(side);
        size_t k;
        for (k = 0; k < len && pos + 1 < outSize; k++) {
            out[pos++] = side[k];
        }
        if (pos + 2 < outSize) {
            if (b->castle == 0) {
                out[pos++] = '-';
            } else {
                if ((b->castle & BB_CASTLE_WK) != 0) {
                    out[pos++] = 'K';
                }
                if ((b->castle & BB_CASTLE_WQ) != 0) {
                    out[pos++] = 'Q';
                }
                if ((b->castle & BB_CASTLE_BK) != 0) {
                    out[pos++] = 'k';
                }
                if ((b->castle & BB_CASTLE_BQ) != 0) {
                    out[pos++] = 'q';
                }
            }
            out[pos++] = ' ';
        }
        if (b->ep >= 0) {
            out[pos++] = (char)('a' + bbFileOf(b->ep));
            out[pos++] = (char)('1' + bbRankOf(b->ep));
        } else {
            out[pos++] = '-';
        }
    }
    out[pos] = '\0';
}

int bbParseUciMove(const BBCore *b, const char *token, BBMove *out)
{
    BBMove legal[256];
    int n = bbGenLegal(b, legal);
    size_t len = strlen(token);
    int i;
    if (len < 4 || len > 5) {
        return 0;
    }
    {
        int f = (int)(token[0] - 'a');
        int r = (int)(token[1] - '1');
        int tf = (int)(token[2] - 'a');
        int tr = (int)(token[3] - '1');
        if (f < 0 || f > 7 || r < 0 || r > 7 || tf < 0 || tf > 7 || tr < 0 || tr > 7) {
            return 0;
        }
        {
            BBSquare from = bbSquare(f, r);
            BBSquare to = bbSquare(tf, tr);
            for (i = 0; i < n; i++) {
                if (bbMoveFrom(legal[i]) == from && bbMoveTo(legal[i]) == to) {
                    BBMove mv = legal[i];
                    char buf[6];
                    bbMoveToUci(mv, buf, sizeof(buf));
                    if (strcmp(buf, token) == 0) {
                        *out = mv;
                        return 1;
                    }
                }
            }
        }
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* SAN notation (generation, parsing, game-status words)              */
/* ------------------------------------------------------------------ */

static char bbSanPieceLetter(int type)
{
    switch (type) {
    case BB_KNIGHT: return 'N';
    case BB_BISHOP: return 'B';
    case BB_ROOK:   return 'R';
    case BB_QUEEN:  return 'Q';
    case BB_KING:   return 'K';
    default:        return '\0';
    }
}

static char bbSanPromoPiece(int flags)
{
    switch (flags) {
    case BB_MOVE_PROMO_Q:
    case BB_MOVE_PROMO_CAP_Q: return 'Q';
    case BB_MOVE_PROMO_R:
    case BB_MOVE_PROMO_CAP_R: return 'R';
    case BB_MOVE_PROMO_B:
    case BB_MOVE_PROMO_CAP_B: return 'B';
    case BB_MOVE_PROMO_N:
    case BB_MOVE_PROMO_CAP_N: return 'N';
    default: return '\0';
    }
}

void bbMoveToSan(const BBCore *b, BBMove move, char *out, size_t outSize)
{
    BBSquare from = bbMoveFrom(move);
    BBSquare to = bbMoveTo(move);
    int flags = bbMoveFlags(move);
    size_t pos = 0;

    if (outSize == 0) {
        return;
    }
    out[0] = '\0';

    if (flags == BB_MOVE_CASTLE_K) {
        static const char kCastleK[] = "O-O";
        size_t i;
        for (i = 0; i < sizeof(kCastleK) - 1 && pos + 1 < outSize; i++) {
            out[pos++] = kCastleK[i];
        }
    } else if (flags == BB_MOVE_CASTLE_Q) {
        static const char kCastleQ[] = "O-O-O";
        size_t i;
        for (i = 0; i < sizeof(kCastleQ) - 1 && pos + 1 < outSize; i++) {
            out[pos++] = kCastleQ[i];
        }
    } else {
        BBPiece piece = b->squares[from];
        int type = bbTypeOf(piece);
        char letter = bbSanPieceLetter(type);
        int otherSameTarget = 0;
        int otherSameFile = 0;
        if (type != BB_KING && type != BB_PAWN) {
            BBMove legal[256];
            int n = bbGenLegal(b, legal);
            int i;
            for (i = 0; i < n; i++) {
                BBMove mv = legal[i];
                if (bbMoveFrom(mv) == from || bbMoveTo(mv) != to) {
                    continue;
                }
                if (bbTypeOf(b->squares[bbMoveFrom(mv)]) != type) {
                    continue;
                }
                otherSameTarget++;
                if (bbFileOf(bbMoveFrom(mv)) == bbFileOf(from)) {
                    otherSameFile++;
                }
            }
        }
        if (letter != '\0') {
            if (pos + 1 < outSize) {
                out[pos++] = letter;
            }
        }
        if (otherSameTarget > 0) {
            /* Disambiguation: rank when every candidate shares the source
             * file (file alone would not separate them), file otherwise. */
            if (otherSameTarget == otherSameFile) {
                if (pos + 1 < outSize) {
                    out[pos++] = (char)('1' + bbRankOf(from));
                }
            } else if (pos + 1 < outSize) {
                out[pos++] = (char)('a' + bbFileOf(from));
            }
        } else if (type == BB_PAWN && bbMoveIsCapture(move)) {
            /* Pawn captures always carry the source file. */
            if (pos + 1 < outSize) {
                out[pos++] = (char)('a' + bbFileOf(from));
            }
        }
        if (bbMoveIsCapture(move)) {
            if (pos + 1 < outSize) {
                out[pos++] = 'x';
            }
        }
        if (pos + 1 < outSize) {
            out[pos++] = (char)('a' + bbFileOf(to));
        }
        if (pos + 1 < outSize) {
            out[pos++] = (char)('1' + bbRankOf(to));
        }
        if (bbSanPromoPiece(flags) != '\0') {
            if (pos + 2 < outSize) {
                out[pos++] = '=';
                out[pos++] = bbSanPromoPiece(flags);
            }
        }
        (void)piece;
    }

    /* Check/mate suffix from the post-move position. */
    {
        BBCore copy;
        BBCoreUndo u;
        copy = *b;
        bbCoreMake(&copy, move, &u);
        if (bbIsCheckmate(&copy)) {
            if (pos + 1 < outSize) {
                out[pos++] = '#';
            }
        } else if (bbInCheck(&copy)) {
            if (pos + 1 < outSize) {
                out[pos++] = '+';
            }
        }
    }
    out[pos] = '\0';
}

static char bbSanFold(char c)
{
    if (c == '0') {
        return 'o';
    }
    if (c >= 'A' && c <= 'Z') {
        return (char)(c - 'A' + 'a');
    }
    return c;
}

static size_t bbSanFoldCopy(const char *san, char *out, size_t outSize)
{
    size_t i = 0;
    size_t pos = 0;
    for (i = 0; san[i] != '\0' && pos + 1 < outSize; i++) {
        char c = san[i];
        if (c == '+' || c == '#' || c == ' ' || c == '\t') {
            continue;
        }
        out[pos++] = bbSanFold(c);
    }
    out[pos] = '\0';
    return pos;
}

int bbParseSan(const BBCore *b, const char *san, BBMove *out)
{
    BBMove legal[256];
    char want[64];
    int n;
    int i;
    size_t wantLen;

    if (san == NULL) {
        return 0;
    }
    wantLen = bbSanFoldCopy(san, want, sizeof(want));
    if (wantLen == 0) {
        return 0;
    }
    n = bbGenLegal(b, legal);
    for (i = 0; i < n; i++) {
        char have[64];
        char folded[64];
        size_t haveLen;
        bbMoveToSan(b, legal[i], have, sizeof(have));
        haveLen = bbSanFoldCopy(have, folded, sizeof(folded));
        if (haveLen == wantLen && memcmp(folded, want, haveLen) == 0) {
            *out = legal[i];
            return 1;
        }
        /* "e8Q" style promotion without the "=". */
        if (haveLen == wantLen + 1 && haveLen >= 2) {
            char stripped[64];
            size_t sPos = 0;
            size_t k;
            for (k = 0; k < haveLen && sPos + 1 < sizeof(stripped); k++) {
                if (folded[k] != '=') {
                    stripped[sPos++] = folded[k];
                }
            }
            stripped[sPos] = '\0';
            if (sPos == wantLen && memcmp(stripped, want, wantLen) == 0) {
                *out = legal[i];
                return 1;
            }
        }
    }
    return 0;
}

void bbGameStatus(const BBCore *b, char *out, size_t outSize)
{
    BBMove legal[256];
    int n;
    if (outSize == 0) {
        return;
    }
    n = bbGenLegal(b, legal);
    if (n == 0) {
        if (bbInCheck(b)) {
            const char *winner = (b->stm == BB_WHITE) ? "black" : "white";
            (void)snprintf(out, outSize, "checkmate %s", winner);
        } else {
            (void)snprintf(out, outSize, "stalemate");
        }
        return;
    }
    if (bbIsRepetition(b) || bbIsFiftyMove(b) || bbInsufficientMaterial(b)) {
        (void)snprintf(out, outSize, "draw");
        return;
    }
    if (bbInCheck(b)) {
        (void)snprintf(out, outSize, "check");
        return;
    }
    (void)snprintf(out, outSize, "active");
}