#pragma once
/* the calls of esp_libc/platform_include/sys/lock.h of ESP-IDF 6.1 that src/ uses */
typedef int _lock_t;
void _lock_acquire(_lock_t *plock);
void _lock_release(_lock_t *plock);
