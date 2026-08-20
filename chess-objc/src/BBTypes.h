/* BBTypes.h — primitive types shared by every component of the chess engine.
 *
 * Pieces are packed as: color-bits | type, e.g. BB_WHITE | BB_KNIGHT.
 * Squares are 0..63 with a1 = 0, h8 = 63 (rank 0 is rank 1, file 0 is a-file).
 * Moves are packed uint16_t: from(6) | to(6) | flags(4).
 */
#ifndef BBTypes_h
#define BBTypes_h

#include <stdint.h>

#define BB_COLOR_MASK 0x18
#define BB_TYPE_MASK  0x07
#define BB_WHITE      0x08
#define BB_BLACK      0x10

enum {
    BB_EMPTY = 0,
    BB_PAWN = 1,
    BB_KNIGHT = 2,
    BB_BISHOP = 3,
    BB_ROOK = 4,
    BB_QUEEN = 5,
    BB_KING = 6
};

/* Move flags, stored in bits 12..15 of a BBMove. */
enum {
    BB_MOVE_QUIET = 0,
    BB_MOVE_DPAWN = 1,
    BB_MOVE_CASTLE_K = 2,
    BB_MOVE_CASTLE_Q = 3,
    BB_MOVE_CAPTURE = 4,
    BB_MOVE_EP = 5,
    BB_MOVE_PROMO_Q = 6,
    BB_MOVE_PROMO_R = 7,
    BB_MOVE_PROMO_B = 8,
    BB_MOVE_PROMO_N = 9,
    BB_MOVE_PROMO_CAP_Q = 10,
    BB_MOVE_PROMO_CAP_R = 11,
    BB_MOVE_PROMO_CAP_B = 12,
    BB_MOVE_PROMO_CAP_N = 13
};

typedef int8_t  BBSquare;   /* 0..63 */
typedef int8_t  BBPiece;    /* BB_EMPTY or color|type */
typedef uint16_t BBMove;    /* from(0..5) to(6..11) flags(12..15) */

/* Castle rights bitmask. */
enum {
    BB_CASTLE_WK = 1,
    BB_CASTLE_WQ = 2,
    BB_CASTLE_BK = 4,
    BB_CASTLE_BQ = 8
};

static inline BBSquare bbSquare(int file, int rank)
{
    return (BBSquare)(file + (rank << 3));
}

static inline int bbFileOf(BBSquare sq)
{
    return sq & 7;
}

static inline int bbRankOf(BBSquare sq)
{
    return sq >> 3;
}

static inline BBSquare bbMirror(BBSquare sq)
{
    return (BBSquare)(sq ^ 56);
}

static inline int bbColorOf(BBPiece piece)
{
    return piece & BB_COLOR_MASK;
}

/* 0/1 index for arrays indexed by colour (BB_WHITE/BB_BLACK are bit masks,
 * not array offsets). */
static inline int bbColorIndex(int color)
{
    return (color == BB_WHITE) ? 0 : 1;
}

static inline int bbTypeOf(BBPiece piece)
{
    return piece & BB_TYPE_MASK;
}

static inline BBMove bbMakeMove(BBSquare from, BBSquare to, int flags)
{
    return (BBMove)((uint16_t)from | ((uint16_t)to << 6) | ((uint16_t)flags << 12));
}

static inline BBSquare bbMoveFrom(BBMove move)
{
    return (BBSquare)(move & 0x3f);
}

static inline BBSquare bbMoveTo(BBMove move)
{
    return (BBSquare)((move >> 6) & 0x3f);
}

static inline int bbMoveFlags(BBMove move)
{
    return (move >> 12) & 0x0f;
}

static inline int bbMoveIsCapture(BBMove move)
{
    unsigned int f = (move >> 12) & 0x0f;
    return (f == BB_MOVE_CAPTURE) || (f == BB_MOVE_EP) || (f >= BB_MOVE_PROMO_CAP_Q);
}

#endif /* BBTypes_h */