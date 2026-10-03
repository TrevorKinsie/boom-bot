package com.boombot.mmo;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.Map;

/** Shared helpers. */
final class Util {
    private Util() {}

    static void mkdirsFor(String path) {
        int slash = Math.max(path.lastIndexOf('/'), path.lastIndexOf('\\'));
        if (slash > 0) {
            try {
                Files.createDirectories(Paths.get(path.substring(0, slash)));
            } catch (IOException e) {
                throw new IllegalStateException("Cannot create directory for " + path + ": " + e.getMessage(), e);
            }
        }
    }

    @SuppressWarnings("unchecked")
    static Map<String, Object> asMap(Object o) {
        return o == null ? new LinkedHashMap<>() : (Map<String, Object>) o;
    }

    static double numDouble(Object o) {
        return o instanceof Number n ? n.doubleValue() : 0.0;
    }

    static long numLong(Object o) {
        return o instanceof Number n ? n.longValue() : 0L;
    }
}