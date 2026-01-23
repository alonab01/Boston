/* Timing-based differential spy on page cache pages using rdtsc.
 *
 * Usage: ./spy_on_diff <path/to/shared/file> [<consider_at_least_pages>]
 *
 * minimal version of spy_on.c that compares adjacent pages to decode a bit
 * 0 if the first page loads faster than the second page -> first page is cached
 * 1 if the second page loads faster than the first page -> second page is cached
 *
 * based on spy_on.c of Novak Boskov <boskov@bu.edu>
 */

#include <sys/mman.h>
#include <sys/stat.h>
#include <errno.h>
#include <unistd.h>
#include <stdio.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <time.h>

#define USE_READ_FOR_PROBING 1
#define OPEN_PER_PAGE 1

// Minimal portion of pages in spied file needed for the file being
// considered accessed. This is kept for compatibility with the original.
static float at_least_pgs = .01;


static inline uint64_t rdtsc(void)
{
    unsigned int lo, hi;
    __asm__ __volatile__("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
}

static inline uint64_t measure_page_access_cycles(int f_map, size_t pg_size, char* buff, int page_to_read, char* file_path)
{
    uint64_t start, end;

    start = rdtsc();
    f_map = open(file_path, O_RDONLY);
    end = rdtsc();
    if (f_map == -1) {
        perror("open");
        exit(errno);
    }
    printf("Open took %lu cycles\n", end - start);

    lseek(f_map, pg_size * page_to_read, SEEK_SET);

    start = rdtsc();
    read(f_map, buff, pg_size);
    end = rdtsc();
    
    close(f_map);
    return end - start;

}


int main(int argc, char *argv[])
{
    int f_map;
    struct stat f_map_stat;
    size_t file_pgs;
    size_t pg_size = sysconf(_SC_PAGESIZE);
    char buff[pg_size];    

    if (argc < 2) {
        printf("Needs 1 arg at least.\n");
        exit(EBADF);
    } 

    f_map = open(argv[1], O_RDONLY);
    if (f_map == -1) {
        printf("Failed to open file %s\n", argv[1]);
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
    
    
    close(f_map);

    //time the entire process to calculate bandwidth
    struct timespec current_time;
    clock_gettime(CLOCK_REALTIME, &current_time);
    time_t begin = current_time.tv_nsec;


    // two measurement in randomized page order and offset
    size_t first = rand() % 2;
    size_t second = 1 - first;
    uint64_t results[2];

    results[first] = measure_page_access_cycles(f_map, pg_size, buff, first, argv[1]);
    results[second] = measure_page_access_cycles(f_map, pg_size, buff, second, argv[1]);
    
    clock_gettime(CLOCK_REALTIME, &current_time);
    time_t end = current_time.tv_nsec;
    
    printf("Page 0: %lu cycles\n",
        results[0]);
    printf("Page 1: %lu cycles\n",
        results[1]);
        
    //print results
    if (results[0] < results[1]) {
        printf("Encoded bit is 0\n");
    } else {
        printf("Encoded bit is 1\n");
    }
    
    printf("Total time: %ld nanoseconds\n", end - begin);
            
    return 0;
}
