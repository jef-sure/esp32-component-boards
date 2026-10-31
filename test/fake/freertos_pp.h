#pragma once
typedef void *SemaphoreHandle_t;
#define pdMS_TO_TICKS(ms) (ms)
#define pdPASS 1
#define portMAX_DELAY 0x7fffffff
int vTaskDelay(int ticks);
#define taskYIELD() ((void)0)
int xTaskCreate(void (*fn)(void *), const char *name, int stack, void *arg, int prio, void *handle);
