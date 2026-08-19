#include "bb_log.h"

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <fstream>
#include <mutex>
#include <sys/stat.h>

namespace bb {
namespace log {

namespace {
std::mutex g_mutex;
Level g_level = Level::Info;
std::string g_error_path = "logs/error.log";
bool g_file_attached = true;

const char* level_name(Level level) {
    switch (level) {
        case Level::Debug: return "DEBUG";
        case Level::Info: return "INFO";
        case Level::Warning: return "WARNING";
        case Level::Error: return "ERROR";
    }
    return "?";
}

std::string timestamp() {
    time_t now = time(nullptr);
    struct tm tmv {};
    localtime_r(&now, &tmv);
    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &tmv);
    return buf;
}
} // namespace

void set_level(Level level) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_level = level;
}

void set_error_log_path(const std::string& path) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_error_path = path;
    g_file_attached = !path.empty();
}

void write(Level level, const std::string& name, const std::string& message) {
    std::string line =
        timestamp() + " - " + name + " - " + level_name(level) + " - " + message;
    std::lock_guard<std::mutex> lock(g_mutex);
    if (static_cast<int>(level) >= static_cast<int>(g_level))
        fprintf(stdout, "%s\n", line.c_str());
    if (g_file_attached && static_cast<int>(level) >= static_cast<int>(Level::Error)) {
        // Ensure the logs directory exists, then append.
        static std::string prev_path;
        if (prev_path != g_error_path) {
            prev_path = g_error_path;
            size_t slash = g_error_path.find_last_of('/');
            if (slash != std::string::npos) {
                std::string dir = g_error_path.substr(0, slash);
                std::string partial;
                for (char c : dir) {
                    partial.push_back(c);
                    if (c == '/') {
                        struct stat st {};
                        if (stat(partial.c_str(), &st) != 0)
                            mkdir(partial.c_str(), 0755);
                    }
                }
                struct stat st {};
                if (stat(dir.c_str(), &st) != 0)
                    mkdir(dir.c_str(), 0755);
            }
        }
        std::ofstream stream(g_error_path, std::ios::app);
        if (stream)
            stream << line << "\n";
    }
}

namespace detail {

std::string sprintf(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    va_list copy;
    va_copy(copy, args);
    int size = std::vsnprintf(nullptr, 0, fmt, copy);
    va_end(copy);
    std::string out;
    if (size < 0) {
        va_end(args);
        return "";
    }
    out.resize(static_cast<size_t>(size));
    std::vsnprintf(out.data(), out.size() + 1, fmt, args);
    va_end(args);
    return out;
}

} // namespace detail

} // namespace log
} // namespace bb