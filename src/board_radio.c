/* The radio beside the chip: started by the adapter of its library, from the table of the glue. */
#include "board_glue.h"
#include "esp_log.h"

static const char *TAG = "board_radio";

bool board_radio_start(void)
{
    static bool started;
    if (started) return true;
    if (board_radio_table.off) {
        ESP_LOGW(TAG, "the radio of the board is off: CONFIG_BOARD_RADIO=y in sdkconfig.defaults turns it on");
        return false;
    }
    for (int i = 0; i < board_radio_table.count; ++i) {
        const struct board_radio_entry *entry = &board_radio_table.entries[i];
        if (entry->start(entry)) {
            started = true;
            return true;
        }
    }
    return false;
}
