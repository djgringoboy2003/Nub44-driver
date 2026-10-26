/* Minimal host test harness shared by the firmware unit tests. */
#ifndef CHECK_H
#define CHECK_H

#include <stdio.h>

static int failures = 0, checks = 0;
#define CHECK(cond, msg) do { checks++; if (!(cond)) { failures++; \
    printf("FAIL %s:%d %s\n", __FILE__, __LINE__, msg); } } while (0)
#define CHECK_SUMMARY() (printf("%d checks, %d failures\n", checks, failures), failures ? 1 : 0)

#endif
