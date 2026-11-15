/*
 * Brings the firmware of the ESP32-C6 beside the ESP32-P4 to a given image without keeping it in flash: it says the
 * version the radio runs, and on "send <bytes>" passes that many bytes from USB to the OTA of the radio. It writes
 * nothing to the flash of the P4: it runs from the place of the program's app, which is flashed again after it.
 */
#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#include "esp_hosted.h"
#include "esp_log.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "board_radio";

/* What the tool on the computer reads: every line of the exchange starts with it. */
#define SAYS "board_radio: "
/* The command that sends an image: the number of its bytes follows. */
#define SEND "send "
/* The OTA of the radio takes at most this much in one write; cp_ota of the clock sends the same. */
#define CHUNK_SIZE 1400
/* Holds the two pieces the computer may send ahead of the confirmations. */
#define USB_BUFFER 4096
#define LINE_SIZE  64
/* The version is said again this often until the tool answers: it may open the port late. */
#define REPEAT_MS 500
/* Bytes that stop coming for this long end a transfer. */
#define IDLE_MS 5000
/* How long the C6 is given to boot the new firmware before the P4 restarts and asks its version again. */
#define SETTLE_MS 2000

static void say(const char *format, ...) __attribute__((format(printf, 1, 2)));
static void say(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    fputs(SAYS, stdout);
    vprintf(format, args);
    fputs("\n", stdout);
    fflush(stdout);
    va_end(args);
}

/* A line from the computer, without its end; false when none came in time. */
static bool read_line(char *line, size_t size, TickType_t wait)
{
    size_t length = 0;
    while (length + 1 < size) {
        char c;
        if (usb_serial_jtag_read_bytes(&c, 1, wait) != 1) return false;
        if (c == '\r') continue;
        if (c == '\n') {
            line[length] = 0;
            return true;
        }
        line[length++] = c;
    }
    line[length] = 0;
    return true;
}

/* Fills the buffer from USB; returns the bytes read, fewer when the computer stopped sending. */
static size_t read_exact(uint8_t *buffer, size_t size)
{
    size_t got = 0;
    while (got < size) {
        int n = usb_serial_jtag_read_bytes(buffer + got, size - got, pdMS_TO_TICKS(IDLE_MS));
        if (n <= 0) break;
        got += (size_t)n;
    }
    return got;
}

static esp_err_t send(size_t size, const esp_hosted_coprocessor_fwver_t *running)
{
    uint8_t  *chunk = malloc(CHUNK_SIZE);
    if (!chunk) return ESP_ERR_NO_MEM;
    esp_err_t ret = esp_hosted_slave_ota_begin();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "esp_hosted_slave_ota_begin: %s", esp_err_to_name(ret));
        free(chunk);
        return ret;
    }
    say("go");
    size_t sent = 0;
    while (sent < size) {
        size_t take = size - sent < CHUNK_SIZE ? size - sent : CHUNK_SIZE;
        if (read_exact(chunk, take) != take) {
            ESP_LOGE(TAG, "the image stopped coming at %u of %u bytes", (unsigned)sent, (unsigned)size);
            ret = ESP_ERR_TIMEOUT;
            break;
        }
        ret = esp_hosted_slave_ota_write(chunk, take);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "esp_hosted_slave_ota_write at %u: %s", (unsigned)sent, esp_err_to_name(ret));
            break;
        }
        sent += take;
        /* the driver drops what does not fit its buffer: the computer sends the next piece only after this */
        say("ok %u", (unsigned)sent);
    }
    free(chunk);
    /* the radio checks the image it was given here, and keeps its running firmware when the image is wrong */
    esp_err_t end = esp_hosted_slave_ota_end();
    if (ret != ESP_OK) return ret;
    if (end != ESP_OK) {
        ESP_LOGE(TAG, "esp_hosted_slave_ota_end: %s", esp_err_to_name(end));
        return end;
    }
    /* a radio of esp_hosted 2.6 and above names the new firmware for boot only when told */
    if (running->major1 > 2 || (running->major1 == 2 && running->minor1 >= 6)) {
        ret = esp_hosted_slave_ota_activate();
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "esp_hosted_slave_ota_activate: %s", esp_err_to_name(ret));
            return ret;
        }
    }
    return ESP_OK;
}

void app_main(void)
{
    usb_serial_jtag_driver_config_t usb = {.rx_buffer_size = USB_BUFFER, .tx_buffer_size = USB_BUFFER};
    esp_err_t                        ret = usb_serial_jtag_driver_install(&usb);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "usb_serial_jtag_driver_install: %s", esp_err_to_name(ret));
        return;
    }
    usb_serial_jtag_vfs_use_driver();

    int rc = esp_hosted_connect_to_slave();
    if (rc != 0) {
        say("no radio %d", rc);
        return;
    }
    esp_hosted_coprocessor_fwver_t running = {0};
    ret = esp_hosted_get_coprocessor_fwversion(&running);
    if (ret != ESP_OK) {
        say("no version %s", esp_err_to_name(ret));
        return;
    }

    char line[LINE_SIZE];
    do {
        say("runs %" PRIu32 ".%" PRIu32 ".%" PRIu32, running.major1, running.minor1, running.patch1);
    } while (!read_line(line, sizeof(line), pdMS_TO_TICKS(REPEAT_MS)));

    if (strncmp(line, SEND, strlen(SEND)) != 0) {
        say("done");
        return;
    }
    size_t size = strtoul(line + strlen(SEND), NULL, 10);
    ret = send(size, &running);
    if (ret != ESP_OK) {
        say("failed %s", esp_err_to_name(ret));
        return;
    }
    say("sent %u", (unsigned)size);
    vTaskDelay(pdMS_TO_TICKS(SETTLE_MS));
    esp_restart();
}
