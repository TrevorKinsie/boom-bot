/* BBUCI.m — UCI protocol driver.
 *
 * Commands: uci, isready, ucinewgame, position, go, stop, quit, setoption,
 * ponderhit (ignored). The search runs on its own thread so that "stop" and
 * "quit" can interrupt it while it is thinking.
 *
 * Non-standard "bb" extension commands used by the Telegram bot:
 *   bb san2uci <san>   -> info string uci <uci>  | info string error <msg>
 *   bb uci2san <uci>   -> info string san <san>  | info string error <msg>
 *   bb fen             -> info string fen <fen>
 *   bb status          -> info string status <word> (bbGameStatus)
 */
#include "BBUCI.h"

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BB_LINE_MAX 4096

static int64_t parseI64(const char *s)
{
    char *end = NULL;
    long long v = strtoll(s, &end, 10);
    if (end == s || *end != '\0') {
        return 0;
    }
    return v;
}

static int parseI32(const char *s)
{
    char *end = NULL;
    long v = strtol(s, &end, 10);
    if (end == s || *end != '\0') {
        return 0;
    }
    return (int)v;
}

static void *uciSearchEntry(void *arg)
{
    BBUCIEngine *self = (BBUCIEngine *)arg;
    [self runSearchThread];
    return NULL;
}

@implementation BBUCIEngine

- (id)init
{
    self = [super init];
    if (self != nil) {
        _searcher = [[BBSearcher alloc] initWithHashBits:18];
        _searchThreadActive = 0;
        bbCoreInit(&_board, NULL);
    }
    return self;
}

- (void)say:(const char *)line
{
    (void)printf("%s\n", line);
    (void)fflush(stdout);
}

- (void)runSearchThread
{
    [_searcher search];
}

/* ------------------------------------------------------------------ */
/* Command handlers                                                   */
/* ------------------------------------------------------------------ */

- (void)handleUci
{
    [self say:"id name BoomBotObjC 1.0"];
    [self say:"id author boom-bot"];
    [self say:"option name Hash type spin default 16 min 1 max 1024"];
    [self say:"uciok"];
}

- (void)handleReady
{
    [self say:"readyok"];
}

- (void)handleNewGame
{
    [_searcher newGame];
}

- (void)handleSetoptionWithTokens:(char **)tokens count:(int)count
{
    int i;
    if (count < 4) {
        return;
    }
    for (i = 1; i + 1 < count; i++) {
        if (strcmp(tokens[i], "name") == 0 && i + 1 < count &&
            strcmp(tokens[i + 1], "Hash") == 0) {
            int mb = 16;
            int j;
            for (j = i + 2; j + 1 < count; j++) {
                if (strcmp(tokens[j], "value") == 0) {
                    mb = parseI32(tokens[j + 1]);
                    break;
                }
            }
            if (mb < 1) {
                mb = 1;
            }
            if (mb > 1024) {
                mb = 1024;
            }
            [_searcher setPosition:&_board];
            (void)mb;
        }
    }
}

- (void)handlePositionWithTokens:(char **)tokens count:(int)count
{
    BBMove mv;
    BBCoreUndo u;
    int firstMoveToken = -1;
    int i;

    if (count < 2) {
        return;
    }
    if (strcmp(tokens[1], "startpos") == 0) {
        bbCoreInit(&_board, NULL);
        firstMoveToken = 2;
    } else if (strcmp(tokens[1], "fen") == 0 && count >= 8) {
        char fen[192];
        size_t pos = 0;
        int f;
        for (f = 2; f < 8 && f < count && pos < sizeof(fen) - 1; f++) {
            size_t len = strlen(tokens[f]);
            if (pos > 0 && pos + 1 < sizeof(fen)) {
                fen[pos++] = ' ';
            }
            if (len > sizeof(fen) - 1 - pos) {
                len = sizeof(fen) - 1 - pos;
            }
            memcpy(fen + pos, tokens[f], len);
            pos += len;
        }
        fen[pos] = '\0';
        bbCoreInit(&_board, fen);
        firstMoveToken = 8;
    } else {
        return;
    }

    for (i = firstMoveToken; i + 1 < count; i++) {
        if (strcmp(tokens[i], "moves") == 0) {
            firstMoveToken = i + 1;
            break;
        }
    }
    if (firstMoveToken < 0) {
        firstMoveToken = count;
    }
    for (i = firstMoveToken; i < count; i++) {
        if (bbParseUciMove(&_board, tokens[i], &mv)) {
            bbCoreMake(&_board, mv, &u);
        }
    }
    if (!_searchThreadActive) {
        [_searcher setPosition:&_board];
    }
}

- (void)handleGoWithTokens:(char **)tokens count:(int)count
{
    int depthLimit = 128;
    int64_t moveTime = -1;
    int64_t wtime = -1;
    int64_t btime = -1;
    int64_t winc = 0;
    int64_t binc = 0;
    int64_t nodes = 0;
    int infinite = 0;
    int hasTimeParam = 0;
    int i;

    for (i = 1; i < count; i++) {
        if (i + 1 >= count) {
            break;
        }
        if (strcmp(tokens[i], "wtime") == 0) {
            wtime = parseI64(tokens[++i]);
            hasTimeParam = 1;
        } else if (strcmp(tokens[i], "btime") == 0) {
            btime = parseI64(tokens[++i]);
            hasTimeParam = 1;
        } else if (strcmp(tokens[i], "winc") == 0) {
            winc = parseI64(tokens[++i]);
            hasTimeParam = 1;
        } else if (strcmp(tokens[i], "binc") == 0) {
            binc = parseI64(tokens[++i]);
            hasTimeParam = 1;
        } else if (strcmp(tokens[i], "movetime") == 0) {
            moveTime = parseI64(tokens[++i]);
        } else if (strcmp(tokens[i], "depth") == 0) {
            depthLimit = parseI32(tokens[++i]);
        } else if (strcmp(tokens[i], "nodes") == 0) {
            nodes = parseI64(tokens[++i]);
        } else if (strcmp(tokens[i], "infinite") == 0) {
            infinite = 1;
        }
    }

    [_searcher setPosition:&_board];
    [_searcher setDepthLimit:depthLimit];
    [_searcher setNodeLimit:nodes];
    if (moveTime > 0) {
        [_searcher setMoveTimeMs:moveTime];
        [_searcher setClockTimeMs:-1 incMs:0];
    } else if (hasTimeParam && !infinite) {
        int64_t ourTime = (_board.stm == BB_WHITE) ? wtime : btime;
        int64_t inc = (_board.stm == BB_WHITE) ? winc : binc;
        [_searcher setClockTimeMs:ourTime incMs:inc];
        [_searcher setMoveTimeMs:-1];
    } else {
        [_searcher setMoveTimeMs:-1];
        [_searcher setClockTimeMs:-1 incMs:0];
    }

    if (_searchThreadActive) {
        [_searcher stopSearch];
        pthread_join(_searchThread, NULL);
        _searchThreadActive = 0;
    }
    pthread_create(&_searchThread, NULL, uciSearchEntry, (void *)self);
    _searchThreadActive = 1;
}

- (void)handleStop
{
    if (_searchThreadActive) {
        [_searcher stopSearch];
        pthread_join(_searchThread, NULL);
        _searchThreadActive = 0;
    }
}

- (void)handleBbWithTokens:(char **)tokens count:(int)count
{
    if (count < 2) {
        return;
    }
    if (strcmp(tokens[1], "san2uci") == 0 && count >= 3) {
        BBMove mv;
        if (bbParseSan(&_board, tokens[2], &mv)) {
            char buf[96];
            char m[6];
            bbMoveToUci(mv, m, sizeof(m));
            (void)snprintf(buf, sizeof(buf), "info string uci %s", m);
            [self say:buf];
        } else {
            [self say:"info string error illegal move"];
        }
    } else if (strcmp(tokens[1], "uci2san") == 0 && count >= 3) {
        BBMove mv;
        if (bbParseUciMove(&_board, tokens[2], &mv)) {
            char buf[96];
            char s[64];
            bbMoveToSan(&_board, mv, s, sizeof(s));
            (void)snprintf(buf, sizeof(buf), "info string san %s", s);
            [self say:buf];
        } else {
            [self say:"info string error illegal move"];
        }
    } else if (strcmp(tokens[1], "play") == 0 && count >= 3) {
        BBMove mv;
        if (bbParseUciMove(&_board, tokens[2], &mv)) {
            BBCoreUndo u;
            bbCoreMake(&_board, mv, &u);
            [self say:"info string ok"];
        } else {
            [self say:"info string error illegal move"];
        }
    } else if (strcmp(tokens[1], "fen") == 0) {
        char buf[256];
        size_t pos = (size_t)snprintf(buf, sizeof(buf), "info string fen ");
        bbToFen(&_board, buf + pos, sizeof(buf) - pos);
        [self say:buf];
    } else if (strcmp(tokens[1], "status") == 0) {
        char buf[128];
        size_t pos;
        (void)snprintf(buf, sizeof(buf), "info string status ");
        pos = strlen(buf);
        bbGameStatus(&_board, buf + pos, sizeof(buf) - pos);
        [self say:buf];
    }
}

/* ------------------------------------------------------------------ */
/* Main loop                                                          */
/* ------------------------------------------------------------------ */

- (void)run
{
    char line[BB_LINE_MAX];
    while (fgets(line, sizeof(line), stdin) != NULL) {
        char *tokens[64];
        int count = 0;
        char *save = NULL;
        char *tok = strtok_r(line, " \t\r\n", &save);
        while (tok != NULL && count < 64) {
            tokens[count++] = tok;
            tok = strtok_r(NULL, " \t\r\n", &save);
        }
        if (count == 0) {
            continue;
        }
        if (strcmp(tokens[0], "uci") == 0) {
            [self handleUci];
        } else if (strcmp(tokens[0], "isready") == 0) {
            [self handleReady];
        } else if (strcmp(tokens[0], "ucinewgame") == 0) {
            [self handleNewGame];
        } else if (strcmp(tokens[0], "position") == 0) {
            [self handlePositionWithTokens:tokens count:count];
        } else if (strcmp(tokens[0], "go") == 0) {
            [self handleGoWithTokens:tokens count:count];
        } else if (strcmp(tokens[0], "stop") == 0) {
            [self handleStop];
        } else if (strcmp(tokens[0], "quit") == 0) {
            [self handleStop];
            break;
        } else if (strcmp(tokens[0], "setoption") == 0) {
            [self handleSetoptionWithTokens:tokens count:count];
        } else if (strcmp(tokens[0], "bb") == 0) {
            [self handleBbWithTokens:tokens count:count];
        }
    }
    if (_searchThreadActive) {
        [_searcher stopSearch];
        pthread_join(_searchThread, NULL);
        _searchThreadActive = 0;
    }
}

@end