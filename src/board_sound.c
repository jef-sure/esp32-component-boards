/*
 * The sound of the board: its hardware set up once by the adapter of its kind, and on demand a task
 * that takes the program's next samples and hands them to that output, whose write waits for the
 * hardware.
 */
#include <string.h>
#include <sys/lock.h>

#include "board_glue.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "board";

enum { SOUND_TASK_STACK = 3072, SOUND_TASK_PRIORITY = 6 };

static _lock_t sound_lock; /* two tasks starting one sound at once get one setup and one task */

static void sound_task(void *arg)
{
    struct board_sound_stream *stream = arg;
    bool                       told   = false;
    for (;;) {
        board_sound_source_t source = stream->source;
        if (source) source(stream->samples, BOARD_SOUND_FRAMES);
        else memset(stream->samples, 0, sizeof(stream->samples));
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
    if (!stream->output && !entry->init(index)) return false;
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
    if (out) *out = (board_sound_t){.rate = entry->rate, .name = entry->name, .index = index};
    return true;
}

bool board_sound_init(board_sound_t *out)
{
    return board_sound_init_at(0, out);
}

bool board_sound_start_at(int index, board_sound_source_t source, uint32_t *rate_out)
{
    if (index < 0 || index >= board_sound_table.count) return false;
    struct board_sound_stream *stream = &board_sound_table.streams[index];
    _lock_acquire(&sound_lock);
    bool ready = sound_ready(index);
    if (ready) {
        stream->source = source;
        if (!stream->running) {
            stream->running = xTaskCreate(sound_task, "sound", SOUND_TASK_STACK, stream, SOUND_TASK_PRIORITY, NULL) == pdPASS;
            if (!stream->running) ESP_LOGE(TAG, "xTaskCreate: sound");
            ready = stream->running;
        }
    }
    _lock_release(&sound_lock);
    if (ready && rate_out) *rate_out = board_sound_table.entries[index].rate;
    return ready;
}

bool board_sound_start(board_sound_source_t source, uint32_t *rate_out)
{
    return board_sound_start_at(0, source, rate_out);
}

void board_sound_source_at(int index, board_sound_source_t source)
{
    if (index >= 0 && index < board_sound_table.count) board_sound_table.streams[index].source = source;
}

void board_sound_source(board_sound_source_t source)
{
    board_sound_source_at(0, source);
}
