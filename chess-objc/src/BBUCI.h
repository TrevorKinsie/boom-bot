/* BBUCI.h — UCI (Universal Chess Interface) protocol loop. */
#ifndef BBUCI_h
#define BBUCI_h

#include <pthread.h>

#include "BBRootObject.h"
#include "BBCore.h"
#include "BBSearch.h"

@interface BBUCIEngine : BBRootObject
{
    BBSearcher *_searcher;
    BBCore _board;
    pthread_t _searchThread;
    int _searchThreadActive;
}

/* Read commands from stdin and drive the searcher until "quit"/EOF. */
- (void)run;

/* Runs one search to completion; called from the search thread. */
- (void)runSearchThread;

@end

#endif /* BBUCI_h */