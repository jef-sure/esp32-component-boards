/*
 * The sound of the board: its hardware set up once by the adapter of its kind, and on demand a task
 * that takes the program's next samples and hands them to that output, whose write waits for the
 * hardware.
 */
#include <string.h>
#include <sys/lock.h>

#include "board_glue.h"
#include "board_volume.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "board";

enum { SOUND_TASK_PRIORITY = 6 };

static _lock_t      sound_lock;                                   /* two tasks starting one sound at once get one setup and one task */
static portMUX_TYPE source_lock = portMUX_INITIALIZER_UNLOCKED; /* the task never takes a source with the context of another */

static void sound_task(void *arg)
{
    struct board_sound_stream *stream = arg;
    bool                       told   = false;
    for (;;) {
        /* held across the source: a change of it waits until the task is out of the previous one */
        xSemaphoreTakeRecursive(stream->busy, portMAX_DELAY);
        taskENTER_CRITICAL(&source_lock);
        board_sound_source_t source = stream->source;
        void                *ctx    = stream->ctx;
        taskEXIT_CRITICAL(&source_lock);
        if (source) source(ctx, stream->samples, BOARD_SOUND_FRAMES);
        else memset(stream->samples, 0, sizeof(stream->samples));
        xSemaphoreGiveRecursive(stream->busy);
        esp_err_t err = stream->output->write(stream->samples, BOARD_SOUND_FRAMES);
        if (err == ESP_OK) continue;
        if (!told) ESP_LOGE(TAG, "%s: %s", stream->output->name, esp_err_to_name(err));
        told = true;
        vTaskDelay(pdMS_TO_TICKS(BOARD_SOUND_FRAMES * 1000 / stream->rate) + 1);
    }
}

void board_glue_sound_ready(int index, const struct board_sound_output *output)
{
    board_sound_table.streams[index].output = output;
}

/* The hardware of a sound set up once; under sound_lock. */
static bool sound_ready(int index)
{
    struct board_sound_stream      *stream = &board_sound_table.streams[index];
    const struct board_sound_entry *entry  = &board_sound_table.entries[index];
    if (!stream->output && !entry->init(index, entry)) return false;
    stream->rate = entry->rate;
    return stream->output != NULL;
}

int board_sound_count(void)
{
    return board_sound_table.count;
}

bool board_sound_init_at(int index, board_sound_t *out)
{
    if (index < 0 || index >= board_sound_table.count) return false;
    _lock_acquire(&sound_lock);
    bool ready = sound_ready(index);
    _lock_release(&sound_lock);
    if (!ready) return false;
    const struct board_sound_entry *entry = &board_sound_table.entries[index];
    if (out) *out = (board_sound_t){.rate = entry->rate, .mixer_volume = board_volume_kept(index, entry->mixer_volume), .name = entry->name, .index = index};
    return true;
}

bool board_sound_init(board_sound_t *out)
{
    return board_sound_init_at(0, out);
}

/* The source of a stream and its context, as one. Once the task runs, the change waits for it to leave the source it is
 * in, so the previous context is not used after this returns; a source may change itself, the lock being recursive. */
static void source_set(struct board_sound_stream *stream, board_sound_source_t source, void *ctx)
{
    if (stream->busy) xSemaphoreTakeRecursive(stream->busy, portMAX_DELAY);
    taskENTER_CRITICAL(&source_lock);
    stream->source = source;
    stream->ctx    = ctx;
    taskEXIT_CRITICAL(&source_lock);
    if (stream->busy) xSemaphoreGiveRecursive(stream->busy);
}

bool board_sound_start_at(int index, board_sound_source_t source, void *ctx, uint32_t *rate_out)
{
    if (index < 0 || index >= board_sound_table.count) return false;
    struct board_sound_stream *stream = &board_sound_table.streams[index];
    _lock_acquire(&sound_lock);
    bool ready = sound_ready(index);
    if (ready) {
        source_set(stream, source, ctx);
        if (!stream->running) {
            if (!stream->busy) stream->busy = xSemaphoreCreateRecursiveMutex();
            if (!stream->busy) ESP_LOGE(TAG, "xSemaphoreCreateRecursiveMutex: sound");
            stream->running = stream->busy && xTaskCreate(sound_task, "sound", CONFIG_BOARD_SOUND_TASK_STACK, stream, SOUND_TASK_PRIORITY, NULL) == pdPASS;
            if (stream->busy && !stream->running) ESP_LOGE(TAG, "xTaskCreate: sound");
            ready = stream->running;
        }
    }
    _lock_release(&sound_lock);
    if (ready && rate_out) *rate_out = board_sound_table.entries[index].rate;
    return ready;
}

bool board_sound_start(board_sound_source_t source, void *ctx, uint32_t *rate_out)
{
    return board_sound_start_at(0, source, ctx, rate_out);
}

void board_sound_source_at(int index, board_sound_source_t source, void *ctx)
{
    if (index >= 0 && index < board_sound_table.count) source_set(&board_sound_table.streams[index], source, ctx);
}

void board_sound_source(board_sound_source_t source, void *ctx)
{
    board_sound_source_at(0, source, ctx);
}
