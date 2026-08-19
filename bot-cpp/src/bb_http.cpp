#include "bb_http.h"

#include "bb_util.h"

#include <fcntl.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>

namespace bb {

namespace {

std::string make_temp_file() {
    char pattern[] = "/tmp/bb_http_XXXXXX";
    int fd = mkstemp(pattern);
    if (fd < 0)
        throw std::runtime_error("mkstemp failed");
    close(fd);
    return std::string(pattern);
}

void write_file(const std::string& path, const std::string& content) {
    int fd = open(path.c_str(), O_WRONLY | O_TRUNC);
    if (fd < 0)
        throw std::runtime_error("cannot open temp file: " + path);
    size_t written = 0;
    while (written < content.size()) {
        ssize_t n = write(fd, content.data() + written, content.size() - written);
        if (n < 0) {
            close(fd);
            throw std::runtime_error("temp file write failed");
        }
        written += static_cast<size_t>(n);
    }
    close(fd);
}

std::string read_file(const std::string& path) {
    int fd = open(path.c_str(), O_RDONLY);
    if (fd < 0)
        return "";
    std::string out;
    char buf[4096];
    while (true) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n <= 0)
            break;
        out.append(buf, static_cast<size_t>(n));
    }
    close(fd);
    return out;
}

std::string read_fd(int fd) {
    std::string out;
    char buf[4096];
    while (true) {
        ssize_t n = read(fd, buf, sizeof(buf));
        if (n <= 0)
            break;
        out.append(buf, static_cast<size_t>(n));
    }
    return out;
}

} // namespace

std::string find_curl() {
    const char* path = std::getenv("PATH");
    if (path == nullptr)
        return "";
    std::string hay = path;
    size_t start = 0;
    while (true) {
        size_t end = hay.find(':', start);
        std::string dir = hay.substr(start, end == std::string::npos ? std::string::npos : end - start);
        if (dir.empty())
            dir = ".";
        std::string candidate = dir + "/curl";
        struct stat st {};
        if (stat(candidate.c_str(), &st) == 0 && (st.st_mode & S_IXUSR))
            return candidate;
        if (end == std::string::npos)
            break;
        start = end + 1;
    }
    return "";
}

HttpResponse http_post(const std::string& url, const std::vector<std::string>& headers,
                       const std::string& body, double timeout_seconds) {
    return http_get(url, headers, timeout_seconds, body);
}

HttpResponse http_get(const std::string& url, const std::vector<std::string>& headers,
                      double timeout_seconds, const std::string& body) {
    HttpResponse response;
    if (timeout_seconds <= 0)
        timeout_seconds = 30.0;

    std::string curl_bin;
    try {
        curl_bin = find_curl();
    } catch (...) {
        curl_bin.clear();
    }
    if (curl_bin.empty()) {
        response.error = "curl binary not found on PATH";
        return response;
    }

    std::string body_file_path = make_temp_file();
    std::string out_file_path = make_temp_file();
    write_file(body_file_path, body);

    int code_pipe[2] = {-1, -1};
    int err_pipe[2] = {-1, -1};
    if (pipe(code_pipe) != 0 || pipe(err_pipe) != 0) {
        unlink(body_file_path.c_str());
        unlink(out_file_path.c_str());
        response.error = "pipe() failed";
        return response;
    }

    pid_t pid = fork();
    if (pid < 0) {
        close(code_pipe[0]);
        close(code_pipe[1]);
        close(err_pipe[0]);
        close(err_pipe[1]);
        unlink(body_file_path.c_str());
        unlink(out_file_path.c_str());
        response.error = "fork() failed";
        return response;
    }

    if (pid == 0) {
        // Child: curl stdout carries the status code, stderr carries errors,
        // response body goes to -o out_file.
        dup2(code_pipe[1], STDOUT_FILENO);
        dup2(err_pipe[1], STDERR_FILENO);
        close(code_pipe[0]);
        close(code_pipe[1]);
        close(err_pipe[0]);
        close(err_pipe[1]);

        std::string max_time = std::to_string(static_cast<int>(timeout_seconds));
        std::string connect_time =
            std::to_string(static_cast<int>(std::min(timeout_seconds, 10.0)));

        std::vector<std::string> args;
        args.push_back(curl_bin);
        args.push_back("--silent");
        args.push_back("--show-error");
        args.push_back("--max-time");
        args.push_back(max_time);
        args.push_back("--connect-timeout");
        args.push_back(connect_time);
        args.push_back("-o");
        args.push_back(out_file_path);
        args.push_back("-w");
        args.push_back("%{http_code}");
        if (!body.empty()) {
            args.push_back("-X");
            args.push_back("POST");
        }
        for (const std::string& header : headers) {
            args.push_back("-H");
            args.push_back(header);
        }
        if (!body.empty()) {
            args.push_back("--data-binary");
            args.push_back("@" + body_file_path);
        }
        args.push_back(url);

        std::vector<char*> argv;
        for (std::string& a : args)
            argv.push_back(a.data());
        argv.push_back(nullptr);

        execv(curl_bin.c_str(), argv.data());
        _exit(127);
    }

    // Parent.
    close(code_pipe[1]);
    close(err_pipe[1]);
    std::string code_out = read_fd(code_pipe[0]);
    std::string err_out = read_fd(err_pipe[0]);
    close(code_pipe[0]);
    close(err_pipe[0]);

    int status = 0;
    waitpid(pid, &status, 0);
    std::string body_out = read_file(out_file_path);
    unlink(body_file_path.c_str());
    unlink(out_file_path.c_str());

    if (WIFEXITED(status) && WEXITSTATUS(status) == 127) {
        response.error = "failed to exec curl";
        return response;
    }
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        response.error = trim(err_out);
        if (response.error.empty())
            response.error = "curl exited with status " + std::to_string(WEXITSTATUS(status));
        return response;
    }

    response.status = std::atoi(trim(code_out).c_str());
    response.body = std::move(body_out);
    response.error = trim(err_out);
    return response;
}

} // namespace bb