/*
 * bb_log.h - minimal leveled logger mirroring Python's logging module.
 *
 * Format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s". By default
 * INFO+ goes to the console and ERROR+ also appends to logs/error.log,
 * matching the wiring in boombot/core/bot.py.
 */
#ifndef BB_LOG_H
#define BB_LOG_H

#include <string>

namespace bb {
namespace log {

enum class Level { Debug = 10, Info = 20, Warning = 30, Error = 40 };

void set_level(Level level);
void set_error_log_path(const std::string& path); // empty disables the file handler

void write(Level level, const std::string& name, const std::string& message);

// Convenience wrappers (module name "bot", matching bot.py's logger wiring).
inline void log_info(const std::string& msg) { write(Level::Info, "bot", msg); }
inline void log_warning(const std::string& msg) { write(Level::Warning, "bot", msg); }
inline void log_error(const std::string& msg) { write(Level::Error, "bot", msg); }

} // namespace log
} // namespace bb

#define BB_LOG(level, name, msg) ::bb::log::write((level), (name), (msg))
#define BB_DEBUG(name, msg) BB_LOG(::bb::log::Level::Debug, name, msg)
#define BB_INFO(name, msg) BB_LOG(::bb::log::Level::Info, name, msg)
#define BB_WARN(name, msg) BB_LOG(::bb::log::Level::Warning, name, msg)
#define BB_ERROR(name, msg) BB_LOG(::bb::log::Level::Error, name, msg)

#define BB_INFO_FMT(name, fmt, ...) \
    ::bb::log::write(::bb::log::Level::Info, name, ::bb::log::detail::sprintf(fmt, __VA_ARGS__))
#define BB_WARN_FMT(name, fmt, ...) \
    ::bb::log::write(::bb::log::Level::Warning, name, ::bb::log::detail::sprintf(fmt, __VA_ARGS__))
#define BB_ERROR_FMT(name, fmt, ...) \
    ::bb::log::write(::bb::log::Level::Error, name, ::bb::log::detail::sprintf(fmt, __VA_ARGS__))

namespace detail {
std::string sprintf(const char* fmt, ...);
} // namespace detail

#endif // BB_LOG_H