/*
 * Static memory runner workload for Firecracker microVM memory footprint benchmarks
 * Compiled with: gcc -O2 -static -o memrunner memrunner.c
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MB (1024 * 1024)

int main(int argc, char **argv) {
    size_t size = 64 * MB;
    if (argc > 1) {
        size = atoi(argv[1]) * MB;
    }

    printf("Allocating and scanning %zu MB...\n", size / MB);
    char *buf = malloc(size);
    if (!buf) {
        perror("malloc failed");
        return 1;
    }

    for (size_t i = 0; i < size; i += 4096) {
        buf[i] = (char)(i & 0xFF);
    }

    printf("Memory scan complete. Touching working set finished.\n");
    free(buf);
    return 0;
}
