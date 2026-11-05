#pragma once
typedef struct QueueDefinition *SemaphoreHandle_t; /* as semphr.h and queue.h of FreeRTOS have it */
SemaphoreHandle_t xSemaphoreCreateRecursiveMutex(void);
int xSemaphoreTakeRecursive(SemaphoreHandle_t mutex, int ticks);
int xSemaphoreGiveRecursive(SemaphoreHandle_t mutex);
#define pdMS_TO_TICKS(ms) (ms)
#define pdPASS 1
#define portMAX_DELAY 0x7fffffff
int vTaskDelay(int ticks);
#define taskYIELD() ((void)0)
int xTaskCreate(void (*fn)(void *), const char *name, int stack, void *arg, int prio, void *handle);
/* the spinlock of a critical section, as portmacro.h and task.h of ESP-IDF 6.1 name it */
typedef struct { int owner, count; } portMUX_TYPE;
#define portMUX_INITIALIZER_UNLOCKED {0, 0}
void taskENTER_CRITICAL(portMUX_TYPE *mux);
void taskEXIT_CRITICAL(portMUX_TYPE *mux);
