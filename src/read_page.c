// read_page.c
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#if !defined(__x86_64__) && !defined(__i386__)
#error "This timing code (RDTSC/RDTSCP/CPUID) is x86-only."
#endif

// -------------------- robust cycle timer: CPUID;RDTSC  ...  RDTSCP;CPUID --------------------

static inline uint64_t tsc_start(void) {
    unsigned hi, lo;
    // CPUID serializes before RDTSC
    __asm__ __volatile__(
        "cpuid\n\t"
        "rdtsc\n\t"
        : "=a"(lo), "=d"(hi)
        : "a"(0)
        : "rbx", "rcx", "memory"
    );
    return ((uint64_t)hi << 32) | lo;
}

static inline uint64_t tsc_end(void) {
    unsigned hi, lo;
    // RDTSCP waits for previous instructions; CPUID serializes after
    __asm__ __volatile__(
        "rdtscp\n\t"
        : "=a"(lo), "=d"(hi)
        :
        : "rcx", "memory"
    );
    __asm__ __volatile__(
        "cpuid\n\t"
        :
        : "a"(0)
        : "rbx", "rcx", "rdx", "memory"
    );
    return ((uint64_t)hi << 32) | lo;
}

static void die(const char *msg) {
    perror(msg);
    exit(1);
}

static void usage(const char *p) {
    fprintf(stderr,
        "Usage:\n"
        "  %s <path> [page_num] [-p A-B|A] [-m]\n"
        "  Pages are 0-based.\n"
        "Options:\n"
        "  -p RANGE   Example: -p 1-100 or -p 7\n"
        "  -m         mmap+load (default: pread)\n",
        p
    );
}

static bool parse_range(const char *s, long *a, long *b) {
    char *dash = strchr(s, '-');
    char *endp = NULL;

    errno = 0;
    long x = strtol(s, &endp, 10);
    if (errno || endp == s) return false;

    if (!dash) {
        if (*endp != '\0') return false;
        *a = x; *b = x;
        return true;
    }

    errno = 0;
    long y = strtol(dash + 1, &endp, 10);
    if (errno || endp == dash + 1) return false;
    if (*endp != '\0') return false;

    *a = x; *b = y;
    return true;
}

static bool is_num(const char *s) {
    if (!s || !*s) return false;
    char *e = NULL;
    errno = 0;
    (void)strtol(s, &e, 10);
    return (!errno && e != s && *e == '\0');
}

// -------------------- probes: timed region contains ONLY the access --------------------

typedef uint64_t (*probe_fn)(void *ctx, off_t off);

struct pread_ctx {
    int fd;
    unsigned char *buf;
};

static inline uint64_t probe_pread(void *vctx, off_t off) {
    struct pread_ctx *ctx = (struct pread_ctx *)vctx;

    uint64_t t0 = tsc_start();
    (void)pread(ctx->fd, ctx->buf, 1, off);   // ONLY the read syscall inside timing
    uint64_t t1 = tsc_end();

    return t1 - t0;
}

struct mmap_ctx {
    volatile unsigned char *map;
};

static inline uint64_t probe_mmap(void *vctx, off_t off) {
    struct mmap_ctx *ctx = (struct mmap_ctx *)vctx;
    uint64_t t0 = tsc_start();
    (void)ctx->map[off];      // volatile load (still forces the load)
    uint64_t t1 = tsc_end();
    return t1 - t0;
}

// -------------------- main --------------------

int main(int argc, char **argv) {
    if (argc < 2) { usage(argv[0]); return 2; }

    const char *path = argv[1];

    // Optional positional page_num
    bool have_pos_page = false;
    long pos_page = 0;
    int opt_start = 2;
    if (argc >= 3 && argv[2][0] != '-' && is_num(argv[2])) {
        have_pos_page = true;
        pos_page = strtol(argv[2], NULL, 10);
        opt_start = 3;
    }

    bool use_mmap = false;
    bool have_range = false;
    long ra = 0, rb = -1;

    optind = opt_start;
    int c;
    while ((c = getopt(argc, argv, "p:mh")) != -1) {
        if (c == 'm') use_mmap = true;
        else if (c == 'p') {
            if (!parse_range(optarg, &ra, &rb)) {
                fprintf(stderr, "Bad -p range: '%s'\n", optarg);
                return 2;
            }
            have_range = true;
        } else {
            usage(argv[0]);
            return (c == 'h') ? 0 : 2;
        }
    }

    int fd = open(path, O_RDONLY);
    if (fd < 0) die("open");

    struct stat st;
    if (fstat(fd, &st) != 0) die("fstat");

    long page_sz = sysconf(_SC_PAGESIZE);
    if (page_sz <= 0) die("sysconf");

    long total_pages = (long)((st.st_size + page_sz - 1) / page_sz);

    long start = 0, end = total_pages - 1;
    if (have_range) { start = ra; end = rb; }
    else if (have_pos_page) { start = pos_page; end = pos_page; }
    if (start > end) { long t = start; start = end; end = t; }
    if (start < 0) start = 0;
    if (end >= total_pages) end = total_pages - 1;

    // Select probe ONCE (no if in the hot loop)
    probe_fn probe = NULL;
    void *probe_ctx = NULL;

    unsigned char buf = 0;
    struct pread_ctx pctx = { .fd = fd, .buf = &buf };
    struct mmap_ctx mctx = {0};

    if (!use_mmap) {
        probe = probe_pread;
        probe_ctx = &pctx;
    } else {
        unsigned char *map = mmap(NULL, (size_t)st.st_size, PROT_READ, MAP_PRIVATE, fd, 0);
        if (map == MAP_FAILED) die("mmap");
        mctx.map = (volatile unsigned char *)map;
        probe = probe_mmap;
        probe_ctx = &mctx;
    }

    // Output cycles (not ns)
    // printf("page_index,offset_bytes,time_cycles\n");
    printf("page_index,time_cycles\n");

    for (long p = start; p <= end; p++) {
        off_t off = (off_t)p * (off_t)page_sz;
        uint64_t dt = probe(probe_ctx, off);
        // printf("%ld,%" PRIdMAX ",%" PRIu64 "\n", p, (intmax_t)off, dt);
        printf("%ld,%" PRIu64 "\n", p, dt);
    }

    if (use_mmap) {
        munmap((void*)mctx.map, (size_t)st.st_size);
    }
    close(fd);
    return 0;
}
