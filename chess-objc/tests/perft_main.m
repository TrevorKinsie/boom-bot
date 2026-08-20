/* perft_main.m — move-generator validation against published perft numbers.
 *
 * Usage:
 *   perft_main                    run the standard suite (startpos..5, others..4)
 *   perft_main <depth>            startpos to that depth (max 6)
 *   perft_main <fen>... <depth>   custom position parsed as one FEN string
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/BBCore.h"

typedef struct PerftCase {
    const char *fen;
    int depth;
    int64_t expected;
} PerftCase;

static int checkCase(const PerftCase *c, int *passed, int *failed)
{
    BBCore board;
    int64_t actual;
    char fenBuf[192];
    bbCoreInit(&board, c->fen);
    bbToFen(&board, fenBuf, sizeof(fenBuf));
    printf("fen   : %s\n", fenBuf);
    actual = bbPerft(&board, c->depth);
    printf("depth %d: expected %lld, got %lld\n", c->depth,
           (long long)c->expected, (long long)actual);
    if (actual == c->expected) {
        (*passed)++;
        printf("PASS\n\n");
        return 0;
    }
    (*failed)++;
    printf("FAIL\n\n");
    return 1;
}

int main(int argc, char **argv)
{
    static const PerftCase suite[] = {
        { "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 5, 4865609 },
        { "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", 4, 4085603 },
        { "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", 5, 674624 },
        { "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", 4, 422333 },
        { "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", 4, 2103487 },
        { "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", 4, 3894594 },
        { "8/8/8/8/8/8/8/K6k w - - 0 1", 3, 54 }
    };
    int passed = 0;
    int failed = 0;
    size_t i;

    if (argc >= 3 && strcmp(argv[1], "fen") == 0) {
        int depth = (int)strtol(argv[argc - 1], NULL, 10);
        char fen[512];
        size_t pos = 0;
        int k;
        for (k = 2; k < argc - 1; k++) {
            size_t len = strlen(argv[k]);
            if (pos > 0 && pos + 1 < sizeof(fen)) {
                fen[pos++] = ' ';
            }
            if (len > sizeof(fen) - 1 - pos) {
                len = sizeof(fen) - 1 - pos;
            }
            memcpy(fen + pos, argv[k], len);
            pos += len;
        }
        fen[pos] = '\0';
        {
            BBCore board;
            bbCoreInit(&board, fen);
            {
                int64_t actual = bbPerft(&board, depth);
                printf("%s depth %d: %lld\n", fen, depth, (long long)actual);
            }
        }
        return 0;
    }

    if (argc == 2) {
        int depth = (int)strtol(argv[1], NULL, 10);
        BBCore board;
        if (depth < 1 || depth > 6) {
            (void)fprintf(stderr, "depth must be 1..6\n");
            return 2;
        }
        bbCoreInit(&board, NULL);
        printf("startpos depth %d: %lld\n", depth,
               (long long)bbPerft(&board, depth));
        return 0;
    }

    for (i = 0; i < sizeof(suite) / sizeof(suite[0]); i++) {
        checkCase(&suite[i], &passed, &failed);
    }
    printf("perft suite: %d passed, %d failed\n", passed, failed);
    return failed == 0 ? 0 : 1;
}