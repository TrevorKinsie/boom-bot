/* unit_main.m — rule/core sanity tests (no GUI, no search thread).
 *
 * Covers: FEN round-trip, make/unmake symmetry, zobrist/repetition,
 * 50-move rule, insufficient material, stalemate/checkmate detection,
 * move parsing, and a mate-in-one search smoke test.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/BBCore.h"
#include "../src/BBEval.h"
#include "../src/BBSearch.h"

static int gFailures = 0;

static void expect(int cond, const char *what)
{
    if (!cond) {
        gFailures++;
        printf("FAIL: %s\n", what);
    } else {
        printf("ok  : %s\n", what);
    }
}

int main(void)
{
    /* --- FEN round trip ------------------------------------------- */
    {
        BBCore b;
        char fen[192];
        bbCoreInit(&b, "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1");
        bbToFen(&b, fen, sizeof(fen));
        expect(strcmp(fen, "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -") == 0,
               "FEN round trip (kiwipete)");
    }

    /* --- make/unmake symmetry ------------------------------------- */
    {
        BBCore b;
        BBCore snapshot;
        BBCoreUndo u;
        BBMove moves[256];
        int n;
        int i;
        bbCoreInit(&b, NULL);
        snapshot = b;
        n = bbGenLegal(&b, moves);
        expect(n == 20, "start position has 20 legal moves");
        for (i = 0; i < n; i++) {
            BBMove buf[256];
            int k;
            bbCoreMake(&b, moves[i], &u);
            expect(bbInCheckSide(&b, BB_WHITE) == 0,
                   "no legal move may leave king in check");
            bbCoreUnmake(&b, &u);
            expect(b.key == snapshot.key && b.stm == snapshot.stm &&
                   b.castle == snapshot.castle && b.ep == snapshot.ep &&
                   b.halfmove == snapshot.halfmove &&
                   memcmp(b.squares, snapshot.squares, sizeof(b.squares)) == 0,
                   "make/unmake restores the position");
            k = bbGenLegal(&b, buf);
            expect(k == n, "move count is stable across make/unmake");
        }
    }

    /* --- en passant + double push ---------------------------------- */
    {
        BBCore b;
        BBCoreUndo u;
        BBCoreUndo u2;
        BBMove mv;

        bbCoreInit(&b, "8/8/8/8/8/8/3P4/4K3 w - - 0 1");
        expect(bbParseUciMove(&b, "d2d4", &mv) == 1, "parser accepts double pawn push");
        bbCoreMake(&b, mv, &u);
        expect(b.ep == 19, "double push sets the ep target square (d3)");
        bbCoreUnmake(&b, &u);

        bbCoreInit(&b, "8/3p4/8/4P3/8/8/8/4K3 w - - 0 1");
        expect(bbParseUciMove(&b, "e1e2", &mv) == 1, "parser accepts quiet king move");
        bbCoreMake(&b, mv, &u);
        expect(bbParseUciMove(&b, "d7d5", &mv) == 1, "parser accepts black double push");
        bbCoreMake(&b, mv, &u2);
        expect(b.ep == 43, "black double push sets the ep square (d6)");
        expect(bbParseUciMove(&b, "e5d6", &mv) == 1, "parser accepts the en passant capture");
        expect(bbMoveFlags(mv) == BB_MOVE_EP, "ep capture carries the EP flag");
        bbCoreMake(&b, mv, &u);
        expect(b.squares[35] == BB_EMPTY, "en passant removes the jumping pawn (d5)");
        expect(b.squares[43] == (BBPiece)(BB_WHITE | BB_PAWN),
               "en passant lands on the target square (d6)");
        bbCoreUnmake(&b, &u);
        expect(b.squares[35] == (BBPiece)(BB_BLACK | BB_PAWN),
               "en passant unmakes and restores the pawn (d5)");
        expect(b.squares[36] == (BBPiece)(BB_WHITE | BB_PAWN),
               "en passant unmake restores the capturing pawn (e5)");
    }

    /* --- promotion ----------------------------------------------- */
    {
        BBCore b;
        BBCoreUndo u;
        BBMove mv;
        bbCoreInit(&b, "8/1P2k3/8/8/8/8/8/4K3 w - - 0 1");
        expect(bbParseUciMove(&b, "b7b8q", &mv) == 1, "parser accepts a promotion");
        bbCoreMake(&b, mv, &u);
        expect(b.squares[57] == (BBPiece)(BB_WHITE | BB_QUEEN),
               "promotion places a queen");
        bbCoreUnmake(&b, &u);
        expect(b.squares[49] == (BBPiece)(BB_WHITE | BB_PAWN) &&
               b.squares[57] == BB_EMPTY,
               "promotion unmakes back to a pawn");
    }

    /* --- repetition & 50-move ------------------------------------- */
    {
        BBCore b;
        BBCoreUndo u;
        BBMove mv;
        static const char *reps[] = { "g1f3", "g8f6", "f3g1", "f6g8",
                                      "g1f3", "g8f6", "f3g1", "f6g8" };
        size_t i;
        bbCoreInit(&b, NULL);
        for (i = 0; i < sizeof(reps) / sizeof(reps[0]); i++) {
            if (!bbParseUciMove(&b, reps[i], &mv)) {
                expect(0, "repetition sequence move parses");
                break;
            }
            bbCoreMake(&b, mv, &u);
            if (i == 6) {
                expect(bbIsRepetition(&b) == 0, "no repetition after 7 plies");
            }
            if (i == 7) {
                expect(bbIsRepetition(&b) == 1, "threefold repetition detected");
            }
        }
    }

    {
        BBCore b;
        bbCoreInit(&b, "8/8/8/8/8/8/8/K6k w - - 99 121");
        expect(bbIsFiftyMove(&b) == 0, "halfmove 99 is not a draw");
        bbCoreInit(&b, "8/8/8/8/8/8/8/K6k w - - 100 121");
        expect(bbIsFiftyMove(&b) == 1, "halfmove 100 is a draw");
    }

    /* --- insufficient material ------------------------------------ */
    {
        BBCore b;
        bbCoreInit(&b, "8/8/8/8/8/8/8/K6k w - - 0 1");
        expect(bbInsufficientMaterial(&b) == 1, "K vs K is drawn");
        bbCoreInit(&b, "4N3/8/8/8/8/8/8/K6k w - - 0 1");
        expect(bbInsufficientMaterial(&b) == 1, "K+N vs K is drawn");
        bbCoreInit(&b, "4B3/8/8/8/8/8/8/K6k w - - 0 1");
        expect(bbInsufficientMaterial(&b) == 1, "K+B vs K is drawn");
        bbCoreInit(&b, "7k/8/8/8/8/8/8/B1B4K w - - 0 1");
        expect(bbInsufficientMaterial(&b) == 1, "K+B vs K+B (same colour) is drawn");
        bbCoreInit(&b, "7k/8/1b6/8/4B3/8/8/K7 w - - 0 1");
        expect(bbInsufficientMaterial(&b) == 0, "K+B vs K+B (opposite colour) is not drawn");
        bbCoreInit(&b, "7k/8/8/4N3/8/8/1n6/K7 w - - 0 1");
        expect(bbInsufficientMaterial(&b) == 0, "K+N vs K+N is not drawn");
    }

    /* --- checkmate / stalemate ------------------------------------ */
    {
        BBCore b;
        bbCoreInit(&b, "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1");
        expect(bbHasLegal(&b) == 0 && bbIsCheckmate(&b) == 1,
               "classic queen+king mate detected");
        bbCoreInit(&b, "7k/8/7K/8/8/8/8/6Q1 b - - 0 1");
        expect(bbInCheck(&b) == 0 && bbHasLegal(&b) == 0 && bbIsCheckmate(&b) == 0,
               "stalemate: no check, no legal moves, not mate");
    }

    /* --- castling rights bookkeeping ------------------------------ */
    {
        BBCore b;
        BBCoreUndo u;
        BBMove mv;
        bbCoreInit(&b, NULL);
        expect(bbParseUciMove(&b, "e2e4", &mv) == 1, "e2e4 parses");
        bbCoreMake(&b, mv, &u);
        expect(b.castle == (BB_CASTLE_WK | BB_CASTLE_WQ | BB_CASTLE_BK | BB_CASTLE_BQ),
               "quiet pawn move keeps all castling rights");
        bbCoreUnmake(&b, &u);
        expect(bbParseUciMove(&b, "e1g1", &mv) == 0, "castling not legal from start");
        {
            BBCore c;
            BBCoreUndo u2;
            bbCoreInit(&c, "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");
            expect(bbParseUciMove(&c, "e1g1", &mv) == 1, "kingside castling parses when legal");
            bbCoreMake(&c, mv, &u2);
            expect(c.squares[bbSquare(6, 0)] == (BBPiece)(BB_WHITE | BB_KING) &&
                   c.squares[bbSquare(5, 0)] == (BBPiece)(BB_WHITE | BB_ROOK),
                   "castling moves king and rook");
            expect(c.castle == (BB_CASTLE_BK | BB_CASTLE_BQ),
                   "kingside castling drops white rights only");
            bbCoreUnmake(&c, &u2);
            expect(c.squares[bbSquare(4, 0)] == (BBPiece)(BB_WHITE | BB_KING) &&
                   c.squares[bbSquare(7, 0)] == (BBPiece)(BB_WHITE | BB_ROOK),
                   "castling unmakes cleanly");
        }
    }

    /* --- score sanity --------------------------------------------- */
    {
        BBCore b;
        bbCoreInit(&b, NULL);
        expect(bbEvaluate(&b) >= -20 && bbEvaluate(&b) <= 20,
               "start position evaluates near zero");
        bbCoreInit(&b, "8/8/8/8/8/8/8/K6k w - - 0 1");
        expect(bbEvaluate(&b) >= -10 && bbEvaluate(&b) <= 10,
               "bare kings evaluate near zero");
        bbCoreInit(&b, "5k2/8/8/8/8/8/8/KQ6 w - - 0 1");
        expect(bbEvaluate(&b) > 700, "queen up evaluates clearly positive");
    }

    /* --- mate-in-one search --------------------------------------- */
    {
        BBCore b;
        BBSearcher *s;
        char best[8];
        bbCoreInit(&b, "7k/8/6K1/8/8/8/6Q1/8 w - - 0 1");
        s = [[BBSearcher alloc] init];
        [s setPosition:&b];
        [s scoreAtDepth:2];
        expect([s bestMoveInto:best size:sizeof(best)] == 0, "search produces a move");
        expect((best[0] == 'g' && best[1] == '2' && best[2] == 'g') ||
               (best[0] == 'g' && best[1] == '2' && best[2] == 'a'),
               "mate in one: queen mates on g7 or a8");
        printf("       best move: %s\n", best);
    }

    /* --- evaluation orders a capture ------------------------------ */
    {
        BBCore b;
        BBSearcher *s;
        char best[8];
        bbCoreInit(&b, "7k/8/8/8/8/4q3/8/K7 w - - 0 1");
        s = [[BBSearcher alloc] init];
        [s setPosition:&b];
        [s scoreAtDepth:1];
        expect([s bestMoveInto:best size:sizeof(best)] == 0 &&
               strcmp(best, "a1a2") == 0, "king declines to walk onto the queen");
        printf("       best move: %s\n", best);
    }

    /* --- SAN round trip over a Ruy Lopez -------------------------- */
    {
        BBCore b;
        BBCoreUndo u;
        BBMove mv;
        char san[64];
        char uci[8];
        static const char *moves[] = { "e2e4", "e7e5", "g1f3", "b8c6",
                                       "f1b5", "a7a6", "b5a4", "g8f6",
                                       "e1g1", "f6e4", "f3e5", "c6e5" };
        static const char *sans[] = { "e4", "e5", "Nf3", "Nc6",
                                      "Bb5", "a6", "Ba4", "Nf6",
                                      "O-O", "Nxe4", "Nxe5", "Nxe5" };
        int passed = 1;
        size_t i;
        bbCoreInit(&b, NULL);
        for (i = 0; i < sizeof(moves) / sizeof(moves[0]); i++) {
            if (!bbParseSan(&b, sans[i], &mv)) {
                printf("       SAN %s rejected at ply %zu\n", sans[i], i);
                passed = 0;
                break;
            }
            bbMoveToSan(&b, mv, san, sizeof(san));
            if (strcmp(san, sans[i]) != 0) {
                printf("       SAN %s rendered as %s\n", sans[i], san);
                passed = 0;
                break;
            }
            bbCoreMake(&b, mv, &u);
        }
        expect(passed, "SAN round trip over the Ruy Lopez");
        bbMoveToUci(mv, uci, sizeof(uci));
        (void)uci;
    }

    /* --- SAN disambiguation --------------------------------------- */
    {
        BBCore b;
        BBMove mv;
        char uci[8];

        /* Two knights (d3, f3) both reaching e5: file disambiguation. */
        bbCoreInit(&b, "k7/8/8/8/8/3N1N3/8/4K3 w - - 0 1");
        expect(bbParseSan(&b, "Ne5", &mv) == 0, "ambiguous Ne5 is rejected");
        expect(bbParseSan(&b, "Nde5", &mv) == 1, "Nde5 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "d3e5") == 0, "Nde5 is d3e5");
        expect(bbParseSan(&b, "Nfe5", &mv) == 1, "Nfe5 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "f3e5") == 0, "Nfe5 is f3e5");

        /* Two rooks on the d-file (d8, d1): rank disambiguation. */
        bbCoreInit(&b, "3r4/k7/8/8/8/8/4K3/3r4 b - - 0 1");
        expect(bbParseSan(&b, "Rd5", &mv) == 0, "ambiguous Rd5 is rejected");
        expect(bbParseSan(&b, "R1d5", &mv) == 1, "R1d5 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "d1d5") == 0, "R1d5 is d1d5");
        expect(bbParseSan(&b, "R8d5", &mv) == 1, "R8d5 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "d8d5") == 0, "R8d5 is d8d5");

        /* Same-file knights (a6, a4): rank disambiguation. */
        bbCoreInit(&b, "8/8/N7/8/N7/8/8/4K2k w - - 0 1");
        expect(bbParseSan(&b, "Nc5", &mv) == 0, "ambiguous Nc5 is rejected");
        expect(bbParseSan(&b, "N4c5", &mv) == 1, "N4c5 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "a4c5") == 0, "N4c5 is a4c5");
        expect(bbParseSan(&b, "N6c5", &mv) == 1, "N6c5 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "a6c5") == 0, "N6c5 is a6c5");

        /* Same-rank knights (a4, c4): file disambiguation. */
        bbCoreInit(&b, "8/8/8/8/N1N5/8/8/4K2k w - - 0 1");
        expect(bbParseSan(&b, "Nb6", &mv) == 0, "ambiguous Nb6 is rejected");
        expect(bbParseSan(&b, "Nab6", &mv) == 1, "Nab6 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "a4b6") == 0, "Nab6 is a4b6");
        expect(bbParseSan(&b, "Ncb6", &mv) == 1, "Ncb6 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "c4b6") == 0, "Ncb6 is c4b6");

        /* Pawn captures keep the source file. */
        bbCoreInit(&b, "k7/8/8/8/3p4/2P5/8/4K3 w - - 0 1");
        expect(bbParseSan(&b, "cxd4", &mv) == 1, "cxd4 resolves");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "c3d4") == 0, "cxd4 is c3d4");
        expect(bbParseSan(&b, "d4", &mv) == 0, "pawn push d4 is not a capture");
    }

    /* --- SAN promotions & castling -------------------------------- */
    {
        BBCore b;
        BBMove mv;
        char san[64];
        char uci[8];

        bbCoreInit(&b, "8/1P2k3/8/8/8/8/8/4K3 w - - 0 1");
        expect(bbParseSan(&b, "b8=Q", &mv) == 1, "promotion SAN b8=Q parses");
        bbMoveToUci(mv, uci, sizeof(uci));
        expect(strcmp(uci, "b7b8q") == 0, "b8=Q maps to b7b8q");
        bbMoveToSan(&b, mv, san, sizeof(san));
        expect(strcmp(san, "b8=Q") == 0, "b7b8q renders as b8=Q");
        expect(bbParseSan(&b, "b8Q", &mv) == 1, "promotion without '=' parses");

        bbCoreInit(&b, "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1");
        expect(bbParseSan(&b, "O-O", &mv) == 1, "kingside castling SAN parses");
        expect(bbMoveFlags(mv) == BB_MOVE_CASTLE_K, "O-O keeps the castle flag");
        expect(bbParseSan(&b, "O-O-O", &mv) == 1 &&
               bbMoveFrom(mv) == bbSquare(4, 0) && bbMoveTo(mv) == bbSquare(2, 0),
               "queenside castling SAN parses");
        bbMoveToSan(&b, mv, san, sizeof(san));
        expect(strcmp(san, "O-O-O") == 0, "queenside castling renders as O-O-O");
        expect(bbParseSan(&b, "0-0", &mv) == 1, "numeric castle form parses");
    }

    /* --- SAN check/mate suffixes ---------------------------------- */
    {
        BBCore b;
        BBCoreUndo u;
        BBMove mv;
        char san[64];
        char status[32];

        bbCoreInit(&b, "7k/1P6/8/8/8/8/8/4K3 w - - 0 1");
        expect(bbParseSan(&b, "b8=Q+", &mv) == 1, "checking promotion parses");
        bbMoveToSan(&b, mv, san, sizeof(san));
        expect(strcmp(san, "b8=Q+") == 0, "checking promotion renders with +");
        bbCoreMake(&b, mv, &u);
        bbGameStatus(&b, status, sizeof(status));
        expect(strcmp(status, "check") == 0, "status reports check after b8=Q+");
        bbCoreUnmake(&b, &u);

        /* c8=Q mate: promotion suffix rendering and status. */
        bbCoreInit(&b, "7k/2P5/6K1/8/8/8/8/8 w - - 0 1");
        expect(bbParseSan(&b, "c8=Q#", &mv) == 1, "mating promotion parses");
        bbMoveToSan(&b, mv, san, sizeof(san));
        expect(strcmp(san, "c8=Q#") == 0, "mating promotion renders with #");
        bbCoreMake(&b, mv, &u);
        bbGameStatus(&b, status, sizeof(status));
        expect(strcmp(status, "checkmate white") == 0,
               "status reports white winner after c8=Q#");
    }

    /* --- game status words ---------------------------------------- */
    {
        BBCore b;
        char status[32];

        bbCoreInit(&b, "8/8/8/8/8/8/8/K6k w - - 0 1");
        bbGameStatus(&b, status, sizeof(status));
        expect(strcmp(status, "draw") == 0, "K vs K reports draw");

        bbCoreInit(&b, "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1");
        bbGameStatus(&b, status, sizeof(status));
        expect(strcmp(status, "checkmate white") == 0,
               "queen mate reports checkmate white");

        bbCoreInit(&b, "7k/8/7K/8/8/8/8/6Q1 b - - 0 1");
        bbGameStatus(&b, status, sizeof(status));
        expect(strcmp(status, "stalemate") == 0, "stalemate reports stalemate");

        bbCoreInit(&b, "R3k3/8/8/8/8/8/8/4K3 b - - 0 1");
        bbGameStatus(&b, status, sizeof(status));
        expect(strcmp(status, "check") == 0, "rook check reports check");
    }

    if (gFailures == 0) {
        printf("\nall unit tests passed\n");
        return 0;
    }
    printf("\n%d unit test(s) failed\n", gFailures);
    return 1;
}