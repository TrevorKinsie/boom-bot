#include "bb_store.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "bb_json.h"
#include "bb_util.h"

/*
 * Error messages may truncate long absolute paths (snprintf, by design);
 * GCC cannot prove the bound, so silence that warning class for this file.
 */
#if defined(__GNUC__)
#pragma GCC diagnostic ignored "-Wformat-truncation"
#endif

/* ----------------------------------------------------- sealing helpers --- */

/* out must hold n + BB_STORE_OVERHEAD bytes.
   Layout: nonce(8) || CTR(payload) || CBC-MAC(nonce || ciphertext). */
static int seal(const bb_store *s, uint64_t nonce, const uint8_t *payload,
                size_t n, uint8_t *out) {
    for (int i = 0; i < 8; i++) {
        out[i] = (uint8_t) (nonce >> (8 * i));
    }
    uint8_t *ct = out + 8;
    memcpy(ct, payload, n);
    bb64_ctr_crypt(&s->enc, out, ct, n);
    uint8_t *mac_input = (uint8_t *) malloc(BB64_BLOCK + n);
    if (mac_input == NULL) {
        return 0;
    }
    memcpy(mac_input, out, BB64_BLOCK); /* nonce */
    memcpy(mac_input + BB64_BLOCK, ct, n);
    bb64_cbc_mac(&s->mac, mac_input, BB64_BLOCK + n, out + 8 + n);
    memset(mac_input, 0, BB64_BLOCK + n);
    free(mac_input);
    return 1;
}

/* Returns 1 when the seal verifies; 0 otherwise. */
static int unseal(const bb_store *s, const uint8_t *sealed, size_t n,
                  uint8_t *plain /* n bytes */) {
    const uint8_t *nonce = sealed;
    const uint8_t *ct = sealed + 8;
    const uint8_t *tag = sealed + 8 + n;
    uint8_t *mac_input = (uint8_t *) malloc(BB64_BLOCK + n);
    if (mac_input == NULL) {
        return 0;
    }
    memcpy(mac_input, nonce, BB64_BLOCK);
    memcpy(mac_input + BB64_BLOCK, ct, n);
    uint8_t expect[BB64_TAG];
    bb64_cbc_mac(&s->mac, mac_input, BB64_BLOCK + n, expect);
    memset(mac_input, 0, BB64_BLOCK + n);
    free(mac_input);
    if (memcmp(expect, tag, BB64_TAG) != 0) {
        return 0;
    }
    memcpy(plain, ct, n);
    bb64_ctr_crypt(&s->enc, nonce, plain, n);
    return 1;
}

/* ------------------------------------------------------------ file I-O --- */

/* Copy the short name of a store file for diagnostics
   (keeps error strings bounded). */
static void base_name(const char *path, char *out, size_t cap) {
    const char *slash = strrchr(path, '/');
    snprintf(out, cap, "%s", slash == NULL ? path : slash + 1);
}

void bb_store_file_path(bb_store *s, const char *user, const char *suffix,
                        char *path, size_t path_size) {
    uint64_t h = bb_splitmix64(bb_splitmix64(0x5345414cULL ^ strlen(user)) ^
                               (uint64_t) user[0]);
    for (const char *it = user; *it != '\0'; it++) {
        h = bb_splitmix64(h ^ (unsigned char) *it);
    }
    char hex[17];
    bb_hex_encode((const uint8_t *) &h, 8, hex);
    snprintf(path, path_size, "%s/u%s.%s", s->dir, hex, suffix);
}

static int read_whole_file(const char *path, uint8_t **out, size_t *out_len) {
    *out = NULL;
    *out_len = 0;
    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        return (errno == ENOENT) ? 1 : -1; /* 1 = absent, -1 = other error */
    }
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return -1;
    }
    long sz = ftell(f);
    if (sz < 0) {
        fclose(f);
        return -1;
    }
    rewind(f);
    uint8_t *buf = (uint8_t *) malloc((size_t) sz ? (size_t) sz : 1);
    if (buf == NULL) {
        fclose(f);
        return -1;
    }
    size_t got = fread(buf, 1, (size_t) sz, f);
    fclose(f);
    if (got != (size_t) sz) {
        free(buf);
        return -1;
    }
    *out = buf;
    *out_len = (size_t) sz;
    return 0;
}

static int write_whole_file(const char *path, const uint8_t *data, size_t n,
                            int use_fsync) {
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (fd < 0) {
        return 0;
    }
    size_t off = 0;
    while (off < n) {
        ssize_t wrote = write(fd, data + off, n - off);
        if (wrote <= 0) {
            close(fd);
            return 0;
        }
        off += (size_t) wrote;
    }
    if (use_fsync) {
        fsync(fd);
    }
    close(fd);
    return 1;
}

static int append_record(const bb_store *s, const char *path, const uint8_t *sealed,
                         size_t n) {
    int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0600);
    if (fd < 0) {
        return 0;
    }
    uint8_t header[4];
    header[0] = (uint8_t) (n & 0xff);
    header[1] = (uint8_t) ((n >> 8) & 0xff);
    header[2] = (uint8_t) ((n >> 16) & 0xff);
    header[3] = (uint8_t) ((n >> 24) & 0xff);
    size_t off = 0;
    while (off < sizeof(header)) {
        ssize_t w = write(fd, header + off, sizeof(header) - off);
        if (w <= 0) {
            close(fd);
            return 0;
        }
        off += (size_t) w;
    }
    off = 0;
    while (off < n) {
        ssize_t w = write(fd, sealed + off, n - off);
        if (w <= 0) {
            close(fd);
            return 0;
        }
        off += (size_t) w;
    }
    if (s->use_fsync) {
        fsync(fd);
    }
    close(fd);
    return 1;
}

/* ------------------------------------------------------------ public --- */

void bb_store_init(bb_store *s, const uint8_t key_enc[16], const uint8_t key_mac[16],
                   const char *data_dir, int use_fsync) {
    memset(s, 0, sizeof(*s));
    bb64_key(&s->enc, key_enc);
    bb64_key(&s->mac, key_mac);
    snprintf(s->dir, sizeof(s->dir), "%s", data_dir);
    s->use_fsync = use_fsync;
}

int bb_store_load(bb_store *s, const char *user, bb_wallet *w) {
    char path[576];
    char err_tmp[256] = {0};

    bb_store_file_path(s, user, "snap", path, sizeof(path));
    uint8_t *snap = NULL;
    size_t snap_len = 0;
    int rc = read_whole_file(path, &snap, &snap_len);
    if (rc < 0) {
        char name[48];

        base_name(path, name, sizeof(name));

        snprintf(s->err, sizeof(s->err), "cannot read snapshot %s: %s",
                 name, strerror(errno));
        return -1;
    }
    if (rc == 0) {
        if (snap_len < 4) {
            snprintf(s->err, sizeof(s->err), "snapshot file too small for magic");
            free(snap);
            return -1;
        }
        uint32_t magic = ((uint32_t) snap[0] << 24) | ((uint32_t) snap[1] << 16) |
                         ((uint32_t) snap[2] << 8) | (uint32_t) snap[3];
        if (magic != BB_STORE_MAGIC) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "snapshot %s has no store magic",
                     name);
            free(snap);
            return -1;
        }
        size_t sealed_n = snap_len - 4;
        if (sealed_n < BB_STORE_OVERHEAD) {
            snprintf(s->err, sizeof(s->err), "snapshot file too small");
            free(snap);
            return -1;
        }
        size_t plain_n = sealed_n - BB_STORE_OVERHEAD;
        uint8_t *plain = (uint8_t *) malloc(plain_n + 1);
        if (plain == NULL) {
            free(snap);
            return -1;
        }
        if (!unseal(s, snap + 4, plain_n, plain)) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "snapshot %s failed authentication",
                     name);
            free(plain);
            free(snap);
            return -1;
        }
        plain[plain_n] = '\0';
        err_tmp[0] = '\0';
        bb_jval *dom = bb_json_parse_err((char *) plain, err_tmp, sizeof(err_tmp));
        free(plain);
        free(snap);
        if (dom == NULL) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "snapshot %s is not JSON",
                     name);
            return -1;
        }
        int ok = bb_wallet_from_json(dom, w);
        bb_json_free(dom);
        if (!ok) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "snapshot %s has invalid wallet state",
                     name);
            return -1;
        }
    } else {
        bb_wallet_init(w); /* no snapshot: fresh wallet */
    }

    bb_store_file_path(s, user, "wlog", path, sizeof(path));
    uint8_t *log = NULL;
    size_t log_len = 0;
    rc = read_whole_file(path, &log, &log_len);
    if (rc < 0) {
        char name[48];

        base_name(path, name, sizeof(name));

        snprintf(s->err, sizeof(s->err), "cannot read event log %s: %s",
                 name, strerror(errno));
        bb_wallet_free(w);
        return -1;
    }
    size_t off = 0;
    while (off < log_len) {
        if (log_len - off < 4) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "event log %s truncated",
                     name);
            free(log);
            bb_wallet_free(w);
            return -1;
        }
        size_t n = (size_t) log[off] | ((size_t) log[off + 1] << 8) |
                   ((size_t) log[off + 2] << 16) | ((size_t) log[off + 3] << 24);
        off += 4;
        if (n < BB_STORE_OVERHEAD || n > BB_STORE_MAX_RECORD || n > log_len - off) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "event log %s has invalid record length",
                     name);
            free(log);
            bb_wallet_free(w);
            return -1;
        }
        size_t plain_n = n - BB_STORE_OVERHEAD;
        uint8_t *plain = (uint8_t *) malloc(plain_n + 1);
        if (plain == NULL) {
            free(log);
            bb_wallet_free(w);
            return -1;
        }
        if (!unseal(s, log + off, plain_n, plain)) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "event log %s failed authentication",
                     name);
            free(plain);
            free(log);
            bb_wallet_free(w);
            return -1;
        }
        plain[plain_n] = '\0';
        err_tmp[0] = '\0';
        bb_jval *dom = bb_json_parse_err((char *) plain, err_tmp, sizeof(err_tmp));
        free(plain);
        if (dom == NULL) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "event log %s is not JSON",
                     name);
            free(log);
            bb_wallet_free(w);
            return -1;
        }
        bb_event ev;
        int ev_ok = bb_event_from_json(dom, &ev);
        bb_json_free(dom);
        if (!ev_ok) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "event log %s has an unreadable event",
                     name);
            free(log);
            bb_wallet_free(w);
            return -1;
        }
        if (ev.seq <= w->seq) {
            off += n; /* already folded into the snapshot */
            continue;
        }
        if (!bb_wallet_apply(w, &ev)) {
            char name[48];

            base_name(path, name, sizeof(name));

            snprintf(s->err, sizeof(s->err), "event log %s violates a wallet invariant",
                     name);
            free(log);
            bb_wallet_free(w);
            return -1;
        }
        off += n;
    }
    free(log);
    return w->exists ? 1 : 0;
}

int bb_store_append(bb_store *s, const char *user, const bb_event *ev) {
    char path[576];
    bb_store_file_path(s, user, "wlog", path, sizeof(path));

    bb_jval *json = bb_event_to_json(ev);
    char *payload = bb_json_to_string(json);
    bb_json_free(json);
    size_t payload_n = strlen(payload);

    uint8_t *sealed = (uint8_t *) malloc(payload_n + BB_STORE_OVERHEAD);
    if (sealed == NULL) {
        free(payload);
        return 0;
    }
    uint64_t nonce = bb_splitmix64((uint64_t) ev->seq * 0x9E3779B97F4A7C15ULL ^
                                   bb_splitmix64((uint64_t) ev->ts));
    if (!seal(s, nonce, (const uint8_t *) payload, payload_n, sealed)) {
        free(payload);
        free(sealed);
        snprintf(s->err, sizeof(s->err), "out of memory sealing event");
        return 0;
    }
    memset(payload, 0, payload_n);
    free(payload);

    int ok = append_record(s, path, sealed, payload_n + BB_STORE_OVERHEAD);
    memset(sealed, 0, payload_n + BB_STORE_OVERHEAD);
    free(sealed);
    if (!ok) {
        char name[48];

        base_name(path, name, sizeof(name));

        snprintf(s->err, sizeof(s->err), "cannot append to %s: %s",
                 name, strerror(errno));
    }
    return ok;
}

int bb_store_snapshot(bb_store *s, const char *user, const bb_wallet *w) {
    char path[576];
    bb_store_file_path(s, user, "snap", path, sizeof(path));

    bb_jval *json = bb_wallet_to_json(w);
    char *payload = bb_json_to_string(json);
    bb_json_free(json);
    size_t payload_n = strlen(payload);

    size_t sealed_n = payload_n + BB_STORE_OVERHEAD;
    uint8_t *sealed = (uint8_t *) malloc(4 + sealed_n);
    if (sealed == NULL) {
        free(payload);
        return 0;
    }
    sealed[0] = (uint8_t) (BB_STORE_MAGIC >> 24);
    sealed[1] = (uint8_t) (BB_STORE_MAGIC >> 16);
    sealed[2] = (uint8_t) (BB_STORE_MAGIC >> 8);
    sealed[3] = (uint8_t) BB_STORE_MAGIC;
    uint64_t nonce = bb_splitmix64((uint64_t) w->seq * 0x45D9F3BULL ^ 0x534e4150ULL);
    if (!seal(s, nonce, (const uint8_t *) payload, payload_n, sealed + 4)) {
        memset(payload, 0, payload_n);
        free(payload);
        free(sealed);
        snprintf(s->err, sizeof(s->err), "out of memory sealing snapshot");
        return 0;
    }
    memset(payload, 0, payload_n);
    free(payload);

    int ok = write_whole_file(path, sealed, 4 + sealed_n, s->use_fsync);
    memset(sealed, 0, 4 + sealed_n);
    free(sealed);
    if (!ok) {
        char name[48];

        base_name(path, name, sizeof(name));

        snprintf(s->err, sizeof(s->err), "cannot write snapshot %s: %s",
                 name, strerror(errno));
    }
    return ok;
}

void bb_store_discard(bb_store *s, const char *user) {
    char path[576];
    bb_store_file_path(s, user, "wlog", path, sizeof(path));
    unlink(path);
    bb_store_file_path(s, user, "snap", path, sizeof(path));
    unlink(path);
}