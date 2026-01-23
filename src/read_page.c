#define _GNU_SOURCE

#include<stdio.h>
#include<time.h>
#include<unistd.h>
#include<string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>

#include <sys/types.h>

#define USE_RDTSC


static int PAGE_SIZE;


static inline uint64_t rdtsc(void) {
    unsigned hi, lo;
    // serialize before reading tsc
    asm volatile("lfence" ::: "memory");
    asm volatile("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
}

/* -------------------------------
   CLOCK_REALTIME in nanoseconds
   ------------------------------- */
static inline uint64_t realtime_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

#ifdef USE_RDTSC

#define CLOCK_FUNC() \
    realtime_ns()

#else
#define CLOCK_FUNC() \
    rdtsc()

#endif

#define COUNTER_FUNC() \
    rdtsc()



int main(int argc, char *argv[]) {

    int f_map;
    int page_to_read = 0;
    long file_sz;
    size_t file_pgs;
    struct stat f_map_stat;
    size_t pg_size = sysconf(_SC_PAGESIZE);
    char buff[pg_size];
    bool verbose = false;
    int arg_idx = 1;
    
    // Declare timing variables at function scope
    clock_t seek_begin = 0, seek_end = 0;
    uint64_t seek_begin_ns = 0, seek_end_ns = 0;
    clock_t map_end = 0;
    uint64_t map_end_ns = 0;

    // Check for -v flag
    if (argc >= 2 && strcmp(argv[1], "-v") == 0) {
        verbose = true;
        arg_idx = 2;
    }

    if (argc < arg_idx + 1) {
        fprintf(stderr, "Usage: %s [-v] <file> [page_number]\n", argv[0]);
        exit(EBADF);
    }
    
    if (argc == arg_idx + 2) {
	page_to_read = atoi(argv[arg_idx + 1]);
    }

    //warm up timers
    CLOCK_FUNC();
    COUNTER_FUNC();



    //time the open
    clock_t open_begin = COUNTER_FUNC();
    uint64_t open_begin_ns = CLOCK_FUNC();
    f_map = open(argv[arg_idx], O_RDONLY );//| O_DIRECT | O_SYNC);
    clock_t open_end = COUNTER_FUNC();
    uint64_t open_end_ns = CLOCK_FUNC();


    if (f_map == -1) {
        fprintf(stderr, "Failed to open file %s\n", argv[arg_idx]);
        exit(errno);
    }

    clock_t stat_begin = COUNTER_FUNC();
    uint64_t stat_begin_ns = CLOCK_FUNC();
    fstat(f_map, &f_map_stat);
    clock_t stat_end = COUNTER_FUNC();
    uint64_t stat_end_ns = CLOCK_FUNC();

    file_pgs = (f_map_stat.st_size + (pg_size - 1)) / pg_size;

    // The arguments to mmap are not of a great importance, we will
    // use these pages just to spy on them. What we try to do here
    // with mapping the file through PROT_WRITE and MAP_SHARED pages
    // is to maximize the probability of being reclaimed. At the end
    // of the day, the main reclaim decision is made by LRU
    // priniciple.
    clock_t map_begin = COUNTER_FUNC();
    uint64_t map_begin_ns = CLOCK_FUNC();

#if MMAP_FILE
    void *mapped_to = mmap(NULL, f_map_stat.st_size,
                           PROT_EXEC, MAP_SHARED, f_map, 0);

    map_end = COUNTER_FUNC();
    map_end_ns = CLOCK_FUNC();
#endif
    if (argc == arg_idx + 2)
    {
        seek_begin = COUNTER_FUNC();
        seek_begin_ns = CLOCK_FUNC();
        file_pgs = 1;
	    lseek(f_map, pg_size * page_to_read, SEEK_SET);
        seek_end = COUNTER_FUNC();
        seek_end_ns = CLOCK_FUNC();
    }
    
    for (size_t i = 0; i < file_pgs; i++)
    {
        
        //double time_spent = 0.0;
        clock_t begin = COUNTER_FUNC();
        uint64_t begin_ns = CLOCK_FUNC();
    
            read(f_map, buff, pg_size);

        clock_t end = COUNTER_FUNC();
        uint64_t end_ns = CLOCK_FUNC();
        
        usleep(3000);

    }
    clock_t total_end = COUNTER_FUNC();
    uint64_t total_end_ns = CLOCK_FUNC();

    // Print CSV header if verbose
    if (verbose) {
        printf("page_size,filename,open_cycles,open_ns,open_ratio,stat_cycles,stat_ns,stat_ratio,file_pages");
#if MMAP_FILE
        printf(",map_cycles,map_ns,map_ratio");
#endif
        if (argc == arg_idx + 2) {
            printf(",seek_pos,page_number,seek_cycles,seek_ns,seek_ratio");
        }
        printf(",total_cycles,total_ns,total_ratio\n");
    }

    // Print CSV data row
    printf("%zu,%s,%lu,%lu,%f,%lu,%lu,%f,%lu",
           pg_size,
           argv[arg_idx],
           (open_end - open_begin),
           (open_end_ns - open_begin_ns),
           (double)(open_end - open_begin) / (double)(open_end_ns - open_begin_ns),
           (stat_end - stat_begin),
           (stat_end_ns - stat_begin_ns),
           (double)(stat_end - stat_begin) / (double)(stat_end_ns - stat_begin_ns),
           file_pgs);
#if MMAP_FILE
    printf(",%lu,%lu,%f",
           (map_end - map_begin),
           (map_end_ns - map_begin_ns),
           (double)(map_end - map_begin) / (double)(map_end_ns - map_begin_ns));
#endif
    if (argc == arg_idx + 2) {
        printf(",0x%llx,%d,%lu,%lu,%f",
               (unsigned long long)(pg_size * page_to_read),
               page_to_read,
               (seek_end - seek_begin),
               (seek_end_ns - seek_begin_ns),
               (double)(seek_end - seek_begin) / (double)(seek_end_ns - seek_begin_ns));
    }
    printf(",%lu,%lu,%f\n",
           (total_end - map_begin),
           (total_end_ns - map_begin_ns),
           (double)(total_end - map_begin) / (double)(total_end_ns - map_begin_ns));

    fflush(stdout);

    close(f_map);
    return 0;
}
