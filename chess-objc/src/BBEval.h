/* BBEval.h — static evaluation (material + piece-square tables + mobility). */
#ifndef BBEval_h
#define BBEval_h

#include <stdint.h>

#include "BBCore.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Score the position in centipawns from White's point of view. */
int32_t bbEvaluate(const BBCore *b);

#ifdef __cplusplus
}
#endif

#endif /* BBEval_h */