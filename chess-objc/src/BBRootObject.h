/* BBRootObject.h — minimal root class base.
 *
 * No Foundation dependency: this project compiles against libobjc only.
 * Objects are created once per process; memory is reclaimed by the OS on
 * exit, so no retain/release/autorelease machinery is needed and none is
 * provided. */
#ifndef BBRootObject_h
#define BBRootObject_h

#include <objc/objc.h>

@interface BBRootObject
{
    char _rootReserved;
}
+ (id)alloc;
- (id)init;
@end

#endif /* BBRootObject_h */