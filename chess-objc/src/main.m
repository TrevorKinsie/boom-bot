/* main.m — entry point: run the UCI loop. */
#include "BBUCI.h"

#include <stdio.h>

int main(void)
{
    /* UCI is a line protocol; flush every line so piped stdin/stdout (the
     * bot's engine client) sees replies immediately. */
    (void)setvbuf(stdout, NULL, _IOLBF, 0);
    (void)setvbuf(stdin, NULL, _IOLBF, 0);

    BBUCIEngine *engine = [[BBUCIEngine alloc] init];
    if (engine == nil) {
        return 1;
    }
    [engine run];
    return 0;
}