/* BBRootObject.m */
#include <objc/runtime.h>

#include "BBRootObject.h"

@implementation BBRootObject

+ (id)alloc
{
    return class_createInstance(self, 0);
}

- (id)init
{
    return self;
}

@end