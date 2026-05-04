#include "spi_frame_rx.h"
#include "pin_config.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

static const char *TAG = "spi_rx";

#define SPI_FRAME_HEADER_SIZE 8
#define SPI_FRAME_MAGIC_0 0xAA
#define SPI_FRAME_MAGIC_1 0x55
#define SPI_MAX_FRAME_SIZE (200 * 1024)
#define SPI_RX_BUF_SIZE 4096
#define SPI_TASK_STACK_SIZE 8192
#define SPI_TASK_PRIORITY 4

#define SPI_HANDSHAKE_PIN GPIO_NUM_6

static spi_device_handle_t s_spi = NULL;
static spi_frame_cb_t s_frame_cb = NULL;
static TaskHandle_t s_task_handle = NULL;
static volatile bool s_running = false;

static bool read_exact(uint8_t *buf, size_t len)
{
    size_t offset = 0;
    while (offset < len) {
        size_t chunk = len - offset;
        if (chunk > SPI_RX_BUF_SIZE) chunk = SPI_RX_BUF_SIZE;

        spi_transaction_t trans = {
            .rx_buffer = buf + offset,
            .rxlength = chunk * 8,
            .length = chunk * 8,
        };
        esp_err_t ret = spi_device_transmit(s_spi, &trans);
        if (ret != ESP_OK) {
            ESP_LOGW(TAG, "SPI transmit failed: %s", esp_err_to_name(ret));
            return false;
        }
        offset += chunk;
    }
    return true;
}

static void spi_rx_task(void *pvParameter)
{
    ESP_LOGI(TAG, "SPI RX task started on core %d", xPortGetCoreID());

    while (s_running) {
        if (gpio_get_level(SPI_HANDSHAKE_PIN) == 0) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        uint8_t header[SPI_FRAME_HEADER_SIZE];
        if (!read_exact(header, SPI_FRAME_HEADER_SIZE)) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        if (header[0] != SPI_FRAME_MAGIC_0 || header[1] != SPI_FRAME_MAGIC_1) {
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        uint32_t frame_len = ((uint32_t)header[2] << 24) |
                              ((uint32_t)header[3] << 16) |
                              ((uint32_t)header[4] << 8)  |
                              ((uint32_t)header[5]);
        uint16_t recv_crc = ((uint16_t)header[6] << 8) | header[7];

        if (frame_len == 0 || frame_len > SPI_MAX_FRAME_SIZE) {
            ESP_LOGW(TAG, "Invalid frame len: %u", (unsigned)frame_len);
            continue;
        }

        uint8_t *frame_buf = heap_caps_malloc(frame_len, MALLOC_CAP_SPIRAM);
        if (!frame_buf) {
            ESP_LOGW(TAG, "No PSRAM for frame (%u)", (unsigned)frame_len);
            size_t skip = frame_len;
            uint8_t dummy[256];
            while (skip > 0) {
                size_t c = skip > sizeof(dummy) ? sizeof(dummy) : skip;
                read_exact(dummy, c);
                skip -= c;
            }
            continue;
        }

        if (!read_exact(frame_buf, frame_len)) {
            ESP_LOGW(TAG, "Frame data read failed (%u bytes)", (unsigned)frame_len);
            free(frame_buf);
            continue;
        }

        uint16_t calc_crc = 0;
        for (uint32_t i = 0; i < frame_len; i++) {
            calc_crc ^= (uint16_t)frame_buf[i] << 8;
            for (int j = 0; j < 8; j++) {
                if (calc_crc & 0x8000) {
                    calc_crc = (calc_crc << 1) ^ 0x1021;
                } else {
                    calc_crc <<= 1;
                }
            }
        }

        if (calc_crc != recv_crc) {
            ESP_LOGW(TAG, "CRC mismatch: got=%04x calc=%04x", recv_crc, calc_crc);
            free(frame_buf);
            continue;
        }

        if (s_frame_cb) {
            s_frame_cb(frame_buf, frame_len);
        }
        free(frame_buf);
    }

    vTaskDelete(NULL);
    s_task_handle = NULL;
}

esp_err_t spi_frame_rx_init(void)
{
    if (s_spi) return ESP_OK;

    gpio_config_t hs_cfg = {
        .pin_bit_mask = (1ULL << SPI_HANDSHAKE_PIN),
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&hs_cfg);

    spi_bus_config_t bus_cfg = {
        .mosi_io_num = SPI_MOSI_PIN,
        .miso_io_num = SPI_MISO_PIN,
        .sclk_io_num = SPI_CLK_PIN,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = SPI_RX_BUF_SIZE,
    };
    esp_err_t ret = spi_bus_initialize(SPI2_HOST, &bus_cfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI bus init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    spi_device_interface_config_t dev_cfg = {
        .clock_speed_hz = 40 * 1000 * 1000,
        .mode = 0,
        .spics_io_num = SPI_CS_PIN,
        .queue_size = 4,
        .flags = SPI_DEVICE_HALFDUPLEX,
    };
    ret = spi_bus_add_device(SPI2_HOST, &dev_cfg, &s_spi);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI device add failed: %s", esp_err_to_name(ret));
        spi_bus_free(SPI2_HOST);
        return ret;
    }

    ESP_LOGI(TAG, "SPI2 initialized (CLK=%d, MOSI=%d, MISO=%d, CS=%d, HS=%d @ 40MHz)",
             SPI_CLK_PIN, SPI_MOSI_PIN, SPI_MISO_PIN, SPI_CS_PIN, SPI_HANDSHAKE_PIN);
    return ESP_OK;
}

esp_err_t spi_frame_rx_register_cb(spi_frame_cb_t cb)
{
    s_frame_cb = cb;
    return ESP_OK;
}

esp_err_t spi_frame_rx_start(void)
{
    if (s_running) return ESP_OK;
    if (!s_spi) return ESP_ERR_INVALID_STATE;

    s_running = true;
    BaseType_t ret = xTaskCreatePinnedToCore(spi_rx_task, "spi_rx",
                                               SPI_TASK_STACK_SIZE, NULL,
                                               SPI_TASK_PRIORITY, &s_task_handle, 1);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create SPI RX task");
        s_running = false;
        return ESP_ERR_NO_MEM;
    }

    ESP_LOGI(TAG, "SPI frame receiver started");
    return ESP_OK;
}

esp_err_t spi_frame_rx_stop(void)
{
    s_running = false;
    if (s_task_handle) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    return ESP_OK;
}

bool spi_frame_rx_is_running(void)
{
    return s_running;
}
