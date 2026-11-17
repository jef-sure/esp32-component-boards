/* The Ethernet of the board: started by the adapter of its library, from the table of the glue. */
#include "board_glue.h"

bool board_glue_ethernet_on;

bool board_ethernet_start(struct esp_netif_obj **netif_out)
{
    static struct esp_netif_obj *started;
    for (int i = 0; !started && i < board_ethernet_table.count; ++i) {
        const struct board_ethernet_entry *entry = &board_ethernet_table.entries[i];
        struct esp_netif_obj              *netif = NULL;
        if (entry->start(entry, &netif)) {
            started                = netif;
            board_glue_ethernet_on = true;
        }
    }
    if (!started) return false;
    if (netif_out) *netif_out = started;
    return true;
}
