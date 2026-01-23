/* This is a minimal poor man's eviction of page cache. Just load a
 * large file in RAM.
 *
 * Author: Novak Boškov <boskov@bu.edu>
 *
 * Created on Dec, 2019.
 *
 * Usage: ./eviction /path/to/a/large/file [create_a_large_file]
 *
 * If the third parameter is passed then creates a file as large as
 * the RAM of the host computer, and loads it.
 */

#include <sys/stat.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdint.h>

#define B_TO_GB 1073741824.0

int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Needs 1 arg.\n");
        return 0;
    } else if (argc == 3) {
        // Create the file as big as RAM
        size_t ram_bytes = sysconf(_SC_PHYS_PAGES) * sysconf(_SC_PAGESIZE);
        float ram_gb = ram_bytes / B_TO_GB;

        printf("A %.2f GB file will be created in %s\n", ram_gb, argv[1]);

        FILE *f_write = fopen(argv[1], "wb");
        char to_write = 0x1;
        int progress = 0;
        for (size_t i = 0; i < ram_bytes; i++) {
            if (i % (int)B_TO_GB == 0)
                printf("%d/%.2f GB...\n", progress++, ram_gb);

            fwrite(&to_write, 1, 1, f_write);
        }
        fclose(f_write);

        printf("A %.2f GB file created in %s\n", ram_gb, argv[1]);
    }

    int pg_size = sysconf(_SC_PAGESIZE);
    int fd = open(argv[1], O_RDONLY);
    struct stat f_stat;
    fstat(fd, &f_stat);
    int pgs_in_f = f_stat.st_size / pg_size;
    int lst_pg_B = f_stat.st_size % pg_size;
    unsigned char *load = malloc(f_stat.st_size);

    printf("Loading %s (%.2fGB)\n"
           "Normally, I would get killed by the kernel when RAM is full.\n"
           "Very stealthy, right? Right?...\n\n",
           argv[1], f_stat.st_size / B_TO_GB);

    // Load file page by page
    for (int i = 0, part = 0; i < pgs_in_f; i++) {
        int ret = read(fd, load + ((uintptr_t)i * pg_size), pg_size);

        if (ret == -1) {
            printf("There is an issue with reading\n");
            exit(1);
        }

        if (i % (pgs_in_f / 10) == 0)
            printf("Read %d%%, file offset: %lu\n", part++ * 10,
                   lseek(fd, 0, SEEK_CUR));
    }

    // If file is not page-aligned, read the remaining bytes
    if (lst_pg_B) {
        int ret = read(fd, load + (pgs_in_f * pg_size), lst_pg_B);
        printf("Tail of %d bytes is read.\n", ret);
    }

    printf("Interrupt program to release RAM.\n");
    // Don't finish the program. Keep RAM occupied if not killed by now.
    for( ; ; ) {}
}
