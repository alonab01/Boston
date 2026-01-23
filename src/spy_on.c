/* Timing-based spy on page cache pages using rdtsc.
 *
 * Usage: ./spy_on <path/to/shared/file> [<consider_at_least_pages>]
 *
 * Similar semantics to the original program, but instead of mincore()
 * we decide page residency via access time: cached pages are faster.
 */

#include <sys/mman.h>
#include <sys/stat.h>
#include <errno.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <time.h>

#define USE_READ_FOR_PROBING 1
#define MMAP_PER_PAGE 0
#define OPEN_PER_PAGE 1

#define MY_MAP_FILE 0

// Minimal portion of pages in spied file needed for the file being
// considered accessed. This is kept for compatibility with the original.
static float at_least_pgs = .01;

// This threshold must be tuned for the platform.
// Rough idea: cached access ~100s of cycles, disk access >> 10^4 cycles.
// Start with something like 2000 and adjust based on measurements.
// static const uint64_t CYCLE_THRESHOLD = 25931470ULL;
static const uint64_t CYCLE_THRESHOLD = 10ULL * 1000ULL * 1000ULL;

static inline uint64_t rdtsc(void)
{
    unsigned int lo, hi;
    __asm__ __volatile__("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
}

static inline uint64_t measure_page_access_cycles(int f_map, size_t pg_size, char* buff, int page_to_read, char* file_path,
                                                    uint64_t *open_cycles, uint64_t *mmap_cycles, uint64_t *read_ns)
{
    uint64_t start, end;
    //rt clock structs
    struct timespec ts_start, ts_end;
    clock_gettime(CLOCK_REALTIME, &ts_start);

#if OPEN_PER_PAGE
    start = rdtsc();
    f_map = open(file_path, O_RDONLY);
    end = rdtsc();
    if (f_map == -1) {
        perror("open");
        exit(errno);
    }
    if (open_cycles) *open_cycles = end - start;
#endif


#if MMAP_PER_PAGE
    start = rdtsc();
    void *mapped_to = mmap(NULL, pg_size,
                           PROT_READ, MAP_SHARED, f_map, pg_size * page_to_read);
    end = rdtsc();
    if (mapped_to == MAP_FAILED) {
        perror("mmap");
        exit(errno);
    }
    if (mmap_cycles) *mmap_cycles = end - start;
#endif

    lseek(f_map, pg_size * page_to_read, SEEK_SET);

    start = rdtsc();
    read(f_map, buff, pg_size);
    end = rdtsc();

    
    #if MMAP_PER_PAGE
    munmap(mapped_to, pg_size);
    #endif
    
    #if OPEN_PER_PAGE
    close(f_map);
    #endif
    
    clock_gettime(CLOCK_REALTIME, &ts_end);

    if (read_ns) {
        *read_ns = (ts_end.tv_sec - ts_start.tv_sec) * 1000000000 +
                   (ts_end.tv_nsec - ts_start.tv_nsec);
    }
    
    return end - start;
}

static inline uint64_t measure_random_page_word_access_cycles(char *page_addr)
{

    uint64_t start = rdtsc();
    volatile int tmp = *(int *)page_addr;
    (void)tmp; // Prevent optimization
    uint64_t end = rdtsc();

    return end - start;
}


int main(int argc, char *argv[])
{
    int f_map;
    struct stat f_map_stat;
    size_t file_pgs;
    size_t pg_size = sysconf(_SC_PAGESIZE);
    char buff[pg_size];
    bool verbose = false;
    int arg_idx = 1;

    // Check for -v flag
    if (argc >= 2 && strcmp(argv[1], "-v") == 0) {
        verbose = true;
        arg_idx = 2;
    }

    if (argc < arg_idx + 1) {
        fprintf(stderr, "Usage: %s [-v] <file> [num_pages] [at_least_pgs]\n", argv[0]);
        exit(EBADF);
    }
    
    // Check if we have the at_least_pgs parameter
    int adjusted_argc = argc - (verbose ? 1 : 0);
    if (adjusted_argc == 4) {
        char *end;
        float f = strtof(argv[arg_idx + 2], &end);
        if (f)
            at_least_pgs = f;
    }

    f_map = open(argv[arg_idx], O_RDONLY);
    if (f_map == -1) {
        fprintf(stderr, "Failed to open file %s\n", argv[arg_idx]);
        exit(errno);
    }

    if (fstat(f_map, &f_map_stat) == -1) {
        perror("fstat");
        close(f_map);
        exit(errno);
    }

    if (f_map_stat.st_size == 0) {
        printf("File is empty.\n");
        close(f_map);
        return 0;
    }
    
    
    file_pgs = (f_map_stat.st_size + (pg_size - 1)) / pg_size;

    if (argc > arg_idx + 1) {
        //override number of pages to consider
        file_pgs = strtoul(argv[arg_idx + 1], NULL, 10);
    }

    if (file_pgs == 0) {
        fprintf(stderr, "Error: file_pgs is 0\n");
        close(f_map);
        return 1;
    }

    // Map the file read-only; we just probe by reading.
    #if MY_MAP_FILE
    char *mapped_to = mmap(NULL, f_map_stat.st_size,
                           PROT_READ, MAP_SHARED, f_map, 0);
    if (mapped_to == MAP_FAILED) {
        perror("mmap");
        close(f_map);
        exit(errno);
    }
#else
    char* mapped_to = NULL;
#endif

#if !MMAP_PER_PAGE || OPEN_PER_PAGE
    close(f_map);
#endif
    // resident_pages[i] == 1 if we think page i is cached, 0 otherwise
    unsigned char resident_pages[file_pgs];

    // Randomized order of page traversal
    size_t *page_indices = malloc(file_pgs * sizeof(size_t));
    if (!page_indices) {
        perror("malloc page_indices");
        #if MY_MAP_FILE
        munmap(mapped_to, f_map_stat.st_size);
        #endif
        exit(1);
    }
    for (size_t i = 0; i < file_pgs; i++)
        page_indices[i] = i;

    // Randomized offset inside each page (word-granularity)
    size_t words_per_page = pg_size / sizeof(int);
    if (words_per_page == 0)
        words_per_page = 1;

    // Timing data collection
    uint64_t total_open_cycles = 0, total_mmap_cycles = 0, total_read_ns = 0;
    uint64_t min_cycles = UINT64_MAX, max_cycles = 0;
    size_t num_measurements = 0;

    if (adjusted_argc == 4) {
        // Poll until enough pages look "hot" 
        do {
            int touched_pgs = 0;

            // Fisher-Yates shuffle of page_indices
            for (size_t i = file_pgs - 1; i > 0; i--) {
                size_t j = (size_t)rand() % (i + 1);
                size_t tmp = page_indices[i];
                page_indices[i] = page_indices[j];
                page_indices[j] = tmp;
            }

            for (size_t idx = 0; idx < file_pgs; idx++) {
                size_t i = page_indices[idx];
                
#if USE_READ_FOR_PROBING || MMAP_PER_PAGE
                uint64_t open_cyc = 0, mmap_cyc = 0, read_ns_val = 0;
                uint64_t cycles = measure_page_access_cycles(f_map, pg_size, buff, i, argv[arg_idx],
                                                              &open_cyc, &mmap_cyc, &read_ns_val);
                total_open_cycles += open_cyc;
                total_mmap_cycles += mmap_cyc;
                total_read_ns += read_ns_val;
                num_measurements++;
                if (cycles < min_cycles) min_cycles = cycles;
                if (cycles > max_cycles) max_cycles = cycles;
#else
                size_t word_index = (size_t)rand() % words_per_page;
                char *page_addr = mapped_to + i * pg_size + word_index * sizeof(int);

                // Clamp to file size
                if ((size_t)(page_addr - mapped_to) >= (size_t)f_map_stat.st_size)
                    continue;

                uint64_t cycles = measure_random_page_word_access_cycles(page_addr);
#endif  

                if (cycles < CYCLE_THRESHOLD) {
                    resident_pages[i] = 1;
                    touched_pgs++;
                } else {
                    resident_pages[i] = 0;
                }
            }

            if (touched_pgs >= at_least_pgs * file_pgs)
                break;

            usleep(5 * 1000);
        } while (1);
    } else {
        // Single measurement in randomized page order and offset
        for (size_t i = file_pgs - 1; i > 0; i--) {
            size_t j = (size_t)rand() % (i + 1);
            size_t tmp = page_indices[i];
            page_indices[i] = page_indices[j];
            page_indices[j] = tmp;
        }

        for (size_t idx = 0; idx < file_pgs; idx++) {
            size_t i = page_indices[idx];
#if USE_READ_FOR_PROBING
            uint64_t open_cyc = 0, mmap_cyc = 0, read_ns_val = 0;
            uint64_t cycles = measure_page_access_cycles(f_map, pg_size, buff, i, argv[arg_idx],
                                                          &open_cyc, &mmap_cyc, &read_ns_val);
            total_open_cycles += open_cyc;
            total_mmap_cycles += mmap_cyc;
            total_read_ns += read_ns_val;
            num_measurements++;
            if (cycles < min_cycles) min_cycles = cycles;
            if (cycles > max_cycles) max_cycles = cycles;
#else
            size_t word_index = (size_t)rand() % words_per_page;
            char *page_addr = mapped_to + i * pg_size + word_index * sizeof(int);

            // Clamp to file size
            if ((size_t)(page_addr - mapped_to) >= (size_t)f_map_stat.st_size)
                continue;
            
            uint64_t cycles = measure_random_page_word_access_cycles(page_addr);
            if (cycles < min_cycles) min_cycles = cycles;
            if (cycles > max_cycles) max_cycles = cycles;
            num_measurements++;
#endif  
            resident_pages[i] = (cycles < CYCLE_THRESHOLD) ? 1 : 0;
        }
    }

    // Print CSV header if verbose
    if (verbose) {
        printf("filename,page_size,file_pages,num_measurements,min_cycles,max_cycles,avg_cycles");
#if OPEN_PER_PAGE
        printf(",avg_open_cycles");
#endif
#if MMAP_PER_PAGE
        printf(",avg_mmap_cycles");
#endif
        printf(",avg_read_ns,resident_pattern\n");
    }

    // Print CSV data row
    uint64_t avg_cycles = num_measurements > 0 ? (min_cycles + max_cycles) / 2 : 0;
    printf("%s,%zu,%zu,%zu,%lu,%lu,%lu",
           argv[arg_idx],
           pg_size,
           file_pgs,
           num_measurements,
           min_cycles,
           max_cycles,
           avg_cycles);
#if OPEN_PER_PAGE
    printf(",%lu", num_measurements > 0 ? total_open_cycles / num_measurements : 0);
#endif
#if MMAP_PER_PAGE
    printf(",%lu", num_measurements > 0 ? total_mmap_cycles / num_measurements : 0);
#endif
    printf(",%lu,", num_measurements > 0 ? total_read_ns / num_measurements : 0);
    
    for (size_t i = 0; i < file_pgs; i++)
        fputc('0' + (resident_pages[i] & 1), stdout);
    printf("\n");
    fflush(stdout);

    free(page_indices);
    #if MY_MAP_FILE
    munmap(mapped_to, f_map_stat.st_size);
    #endif

    #if MMAP_PER_PAGE && !OPEN_PER_PAGE
    close(f_map);
    #endif


    return 0;
}
