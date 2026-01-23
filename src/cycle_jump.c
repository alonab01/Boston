#include <stdio.h>
#include <stdint.h>



static inline uint64_t rdtsc(void) {
    unsigned hi, lo;
    // serialize before reading tsc
    asm volatile("lfence" ::: "memory");
    asm volatile("rdtsc" : "=a"(lo), "=d"(hi));
    return ((uint64_t)hi << 32) | lo;
}

int main() {
    //run a tight loop and print when we have a jump in rdtsc values
    uint64_t last = rdtsc();
    while (1) {
        uint64_t curr = rdtsc();
        if (curr - last > 100) {
            printf("Cycle jump detected: %lu -> %lu (diff=%lu)\n", last, curr, curr - last);
        }
        last = rdtsc(); //dont count the printf time
    }

}