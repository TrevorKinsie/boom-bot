/*
 * bb_http.h - minimal HTTPS client built on the curl binary.
 *
 * The dependency-free build constraint rules out linking OpenSSL/libcurl,
 * so HTTPS requests are issued by spawning the system curl binary (already
 * installed in the Docker image and on typical dev hosts). This mirrors the
 * repo's process-orchestration idiom (JVM decision engine, Stockfish).
 */
#ifndef BB_HTTP_H
#define BB_HTTP_H

#include <string>
#include <vector>

namespace bb {

struct HttpResponse {
    int status = 0;          // HTTP status code (0 on transport failure)
    std::string body;        // response body (raw bytes, UTF-8 JSON)
    std::string error;       // curl stderr / error text on failure

    bool ok() const { return status >= 200 && status < 300; }
};

// POST with a JSON body and optional extra headers (e.g. Authorization).
HttpResponse http_post(const std::string& url,
                       const std::vector<std::string>& headers,
                       const std::string& body,
                       double timeout_seconds);

// GET request; the optional body is sent when non-empty.
HttpResponse http_get(const std::string& url,
                      const std::vector<std::string>& headers,
                      double timeout_seconds,
                      const std::string& body = "");

// Returns the path of a usable curl binary, or empty when not found.
std::string find_curl();

} // namespace bb

#endif // BB_HTTP_H