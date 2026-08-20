/* BBEval.m — static evaluation.
 *
 * Material + piece-square tables (classic "simplified evaluation" tables in
 * rank-8-first visual order), a bishop-pair bonus, a small mobility term and
 * a tempo bonus for the side to move. King PSTs switch to the endgame table
 * once the heavy material count drops.
 */
#include "BBEval.h"

#define BB_MATERIAL_PAWN   100
#define BB_MATERIAL_KNIGHT 320
#define BB_MATERIAL_BISHOP 330
#define BB_MATERIAL_ROOK   500
#define BB_MATERIAL_QUEEN  900
#define BB_BISHOP_PAIR     30
#define BB_TEMPO           10
#define BB_ENDGAME_THRESHOLD 2600

static const int gPstPawn[64] = {
      0,   0,   0,   0,   0,   0,   0,   0,
     50,  50,  50,  50,  50,  50,  50,  50,
     10,  10,  20,  30,  30,  20,  10,  10,
      5,   5,  10,  25,  25,  10,   5,   5,
      0,   0,   0,  20,  20,   0,   0,   0,
      5,  -5, -10,   0,   0, -10,  -5,   5,
      5,  10,  10, -20, -20,  10,  10,   5,
      0,   0,   0,   0,   0,   0,   0,   0
};

static const int gPstKnight[64] = {
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50
};

static const int gPstBishop[64] = {
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20
};

static const int gPstRook[64] = {
      0,   0,   0,   0,   0,   0,   0,   0,
      5,  10,  10,  10,  10,  10,  10,   5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
      0,   0,   0,   5,   5,   0,   0,   0
};

static const int gPstQueen[64] = {
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20
};

static const int gPstKingMid[64] = {
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20
};

static const int gPstKingEnd[64] = {
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -30,   0,   0,   0,   0, -30, -30,
    -50, -30, -30, -30, -30, -30, -50, -50
};

/* Tables are written rank 8 first (visual order): white pieces index them by
 * their visual position, black pieces just by square (black's rank-1 squares
 * map onto the values the table holds for white's rank-8). */
static inline int pstIndex(int color, BBSquare sq)
{
    if (color == BB_WHITE) {
        return (7 - bbRankOf(sq)) * 8 + bbFileOf(sq);
    }
    return sq;
}

int32_t bbEvaluate(const BBCore *b)
{
    int score = 0;
    int bishopsA[2] = { 0, 0 };
    int heavyMaterial = 0;
    int mobility = 0;
    int i;

    /* Pass 1: how much heavy material remains (king PST phase switch). */
    for (i = 0; i < 64; i++) {
        switch (bbTypeOf(b->squares[i])) {
        case BB_KNIGHT:
            heavyMaterial += BB_MATERIAL_KNIGHT;
            break;
        case BB_BISHOP:
            heavyMaterial += BB_MATERIAL_BISHOP;
            break;
        case BB_ROOK:
            heavyMaterial += BB_MATERIAL_ROOK;
            break;
        case BB_QUEEN:
            heavyMaterial += BB_MATERIAL_QUEEN;
            break;
        default:
            break;
        }
    }

    for (i = 0; i < 64; i++) {
        BBPiece pc = b->squares[i];
        int color;
        int type;
        int sign;
        int idx;
        if (pc == BB_EMPTY) {
            continue;
        }
        color = bbColorOf(pc);
        type = bbTypeOf(pc);
        sign = (color == BB_WHITE) ? 1 : -1;
        idx = pstIndex(color, (BBSquare)i);

        switch (type) {
        case BB_PAWN:
            score += sign * (BB_MATERIAL_PAWN + gPstPawn[idx]);
            break;
        case BB_KNIGHT:
            score += sign * (BB_MATERIAL_KNIGHT + gPstKnight[idx]);
            mobility += sign * bbLitMoves(b, (BBSquare)i, pc);
            break;
        case BB_BISHOP:
            bishopsA[color == BB_WHITE ? 0 : 1]++;
            score += sign * (BB_MATERIAL_BISHOP + gPstBishop[idx]);
            mobility += sign * bbLitMoves(b, (BBSquare)i, pc);
            break;
        case BB_ROOK:
            score += sign * (BB_MATERIAL_ROOK + gPstRook[idx]);
            mobility += sign * bbLitMoves(b, (BBSquare)i, pc);
            break;
        case BB_QUEEN:
            score += sign * (BB_MATERIAL_QUEEN + gPstQueen[idx]);
            mobility += sign * bbLitMoves(b, (BBSquare)i, pc);
            break;
        case BB_KING:
            if (heavyMaterial <= BB_ENDGAME_THRESHOLD) {
                score += sign * gPstKingEnd[idx];
            } else {
                score += sign * gPstKingMid[idx];
            }
            break;
        default:
            break;
        }
    }

    /* Bishop pair + mobility. */
    if (bishopsA[0] >= 2) {
        score += BB_BISHOP_PAIR;
    }
    if (bishopsA[1] >= 2) {
        score -= BB_BISHOP_PAIR;
    }
    score += mobility;

    /* Tempo. */
    if (b->stm == BB_WHITE) {
        score += BB_TEMPO;
    } else {
        score -= BB_TEMPO;
    }

    return (int32_t)score;
}