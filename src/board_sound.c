/*
 * The task of the sound: it takes the program's next samples and hands them to the output of the
 * board's kind of sound, whose write waits for the hardware.
 */
#include <string.h>

#include "board_glue.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "board";

enum { SOUND_TASK_STACK = 3072, SOUND_TASK_PRIORITY = 6 };

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

bool board_glue_sound_run(int index, const struct board_sound_output *output, uint32_t rate, board_sound_source_t source)
{
    struct board_sound_stream *stream = &board_sound_table.streams[index];
    stream->source                    = source;
    stream->rate                      = rate;
    stream->output                    = output;
    if (xTaskCreate(sound_task, "sound", SOUND_TASK_STACK, stream, SOUND_TASK_PRIORITY, NULL) != pdPASS) {
        ESP_LOGE(TAG, "xTaskCreate: sound");
        stream->output = NULL;
        return false;
    }
    return true;
}

int board_sound_count(void)
{
    return board_sound_table.count;
}

bool board_sound_start_at(int index, board_sound_source_t source, uint32_t *rate_out)
{
    if (index < 0 || index >= board_sound_table.count) return false;
    const struct board_sound_entry *entry = &board_sound_table.entries[index];
    if (board_sound_table.streams[index].output) board_sound_table.streams[index].source = source;
    else if (!entry->start(index, source)) return false;
    if (rate_out) *rate_out = entry->rate;
    return true;
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
