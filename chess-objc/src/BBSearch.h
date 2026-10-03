/* BBSearch.h — iterative-deepening alpha-beta searcher (ObjC driver around a
 * C engine core). Output: UCI "info" lines on stdout during the search and a
 * final "bestmove m" line. */
#ifndef BBSearch_h
#define BBSearch_h

#include <stdint.h>
#include <stddef.h>

#include "BBCore.h"
#include "BBRootObject.h"

struct BBEngine;

@interface BBSearcher : BBRootObject
{
    struct BBEngine *_engine;
}

- (id)init;
- (id)initWithHashBits:(int)bits;

/* Replace the root position (deep copy; must be done between searches). */
- (void)setPosition:(const BBCore *)pos;

/* Search limits; all default to "unlimited" until set. */
- (void)setDepthLimit:(int)depth;
- (void)setMoveTimeMs:(int64_t)ms;
- (void)setClockTimeMs:(int64_t)ourTime incMs:(int64_t)inc;
- (void)setNodeLimit:(int64_t)limit;

/* Clear the transposition table and search state. */
- (void)newGame;

/* Run until the time/depth/node budget is used up. Blocks the calling
 * thread; emits "info" lines and finally "bestmove". */
- (void)search;

/* Signal a running -search (called from another thread) to stop early. */
- (void)stopSearch;

/* Synchronous helper for tests: run one fixed-depth search and return the
 * engine's score for the chosen root move. */
- (int32_t)scoreAtDepth:(int)depth;

/* Last chosen root move in UCI notation (stable after -search or
 * -scoreAtDepth:). Returns 0 on success. */
- (int)bestMoveInto:(char *)buf size:(size_t)size;

/* Nodes searched by the most recent -search. */
- (int64_t)nodesSearched;

@end

#endif /* BBSearch_h */