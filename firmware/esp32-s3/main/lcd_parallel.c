#include "lcd_parallel.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include <string.h>

static const char *TAG = "lcd_par";

#define ILI9486_SWRESET 0x01
#define ILI9486_SLPIN   0x10
#define ILI9486_SLPOUT  0x11
#define ILI9486_NORON   0x13
#define ILI9486_INVOFF  0x20
#define ILI9486_INVON   0x21
#define ILI9486_DISPOFF 0x28
#define ILI9486_DISPON  0x29
#define ILI9486_CASET   0x2A
#define ILI9486_RASET   0x2B
#define ILI9486_RAMWR   0x2C
#define ILI9486_MADCTL  0x36
#define ILI9486_COLMOD  0x3A
#define ILI9486_IFCTL   0xF0
#define ILI9486_FRMCTR1 0xB1
#define ILI9486_INVCTR  0xB4
#define ILI9486_PWCTR1  0xC0
#define ILI9486_PWCTR2  0xC1
#define ILI9486_PWCTR3  0xC2
#define ILI9486_VMCTR1  0xC5

#define LCD_STRIP_MAX_BYTES 65536

static bool on_color_trans_done(esp_lcd_panel_io_handle_t panel_io,
                                 esp_lcd_panel_io_event_data_t *edata,
                                 void *user_ctx)
{
    (void)panel_io;
    (void)edata;
    lcd_parallel_handle_t *handle = (lcd_parallel_handle_t *)user_ctx;
    if (handle && handle->trans_done_sem) {
        BaseType_t high_task_wakeup = pdFALSE;
        xSemaphoreGiveFromISR(handle->trans_done_sem, &high_task_wakeup);
        return (high_task_wakeup == pdTRUE);
    }
    return false;
}

static void lcd_set_window(esp_lcd_panel_io_handle_t io,
                            uint16_t x0, uint16_t y0,
                            uint16_t x1, uint16_t y1)
{
    uint8_t caset[] = {(x0 >> 8) & 0xFF, x0 & 0xFF, (x1 >> 8) & 0xFF, x1 & 0xFF};
    esp_lcd_panel_io_tx_param(io, ILI9486_CASET, caset, 4);
    uint8_t raset[] = {(y0 >> 8) & 0xFF, y0 & 0xFF, (y1 >> 8) & 0xFF, y1 & 0xFF};
    esp_lcd_panel_io_tx_param(io, ILI9486_RASET, raset, 4);
}

static esp_err_t ili9486_init(esp_lcd_panel_io_handle_t io, int width, int height, uint8_t madctl)
{
    esp_lcd_panel_io_tx_param(io, ILI9486_SWRESET, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(200));

    esp_lcd_panel_io_tx_param(io, ILI9486_SLPOUT, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(120));

    uint8_t ifctl[] = {0x01, 0x00, 0x00};
    esp_lcd_panel_io_tx_param(io, ILI9486_IFCTL, ifctl, 3);

    uint8_t pwctr1[] = {0x0F, 0x0F};
    esp_lcd_panel_io_tx_param(io, ILI9486_PWCTR1, pwctr1, 2);

    uint8_t pwctr2[] = {0x41};
    esp_lcd_panel_io_tx_param(io, ILI9486_PWCTR2, pwctr2, 1);

    uint8_t pwctr3[] = {0x22};
    esp_lcd_panel_io_tx_param(io, ILI9486_PWCTR3, pwctr3, 1);

    uint8_t vmctr1[] = {0x00, 0x16};
    esp_lcd_panel_io_tx_param(io, ILI9486_VMCTR1, vmctr1, 2);

    uint8_t invctr[] = {0x00};
    esp_lcd_panel_io_tx_param(io, ILI9486_INVCTR, invctr, 1);

    uint8_t frmctr1[] = {0xA0};
    esp_lcd_panel_io_tx_param(io, ILI9486_FRMCTR1, frmctr1, 1);

    uint8_t pgc[] = {0x0F, 0x1F, 0x1C, 0x0C, 0x0F, 0x08, 0x48, 0x98,
                     0x37, 0x0A, 0x13, 0x04, 0x11, 0x0D, 0x00, 0x00};
    esp_lcd_panel_io_tx_param(io, 0xE0, pgc, 16);

    uint8_t ngc[] = {0x0F, 0x32, 0x2E, 0x0B, 0x0D, 0x05, 0x47, 0x75,
                     0x37, 0x06, 0x10, 0x03, 0x24, 0x20, 0x00, 0x00};
    esp_lcd_panel_io_tx_param(io, 0xE1, ngc, 16);

    esp_lcd_panel_io_tx_param(io, ILI9486_INVOFF, NULL, 0);

    uint8_t madctl_val[] = {madctl};
    esp_lcd_panel_io_tx_param(io, ILI9486_MADCTL, madctl_val, 1);

    uint8_t colmod[] = {0x55};
    esp_lcd_panel_io_tx_param(io, ILI9486_COLMOD, colmod, 1);

    esp_lcd_panel_io_tx_param(io, ILI9486_NORON, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(20));

    esp_lcd_panel_io_tx_param(io, ILI9486_DISPON, NULL, 0);
    vTaskDelay(pdMS_TO_TICKS(100));

    ESP_LOGI(TAG, "ILI9486 init done (%dx%d, MADCTL=0x%02X)", width, height, madctl);
    return ESP_OK;
}

esp_err_t lcd_parallel_init(const lcd_parallel_config_t *config, lcd_parallel_handle_t *handle)
{
    memcpy(&handle->cfg, config, sizeof(lcd_parallel_config_t));
    handle->bus = NULL;
    handle->io = NULL;
    handle->initialized = false;

    handle->mutex = xSemaphoreCreateMutex();
    if (!handle->mutex) return ESP_ERR_NO_MEM;

    handle->trans_done_sem = xSemaphoreCreateBinary();
    if (!handle->trans_done_sem) return ESP_ERR_NO_MEM;

    int pclk_hz = config->pclk_hz > 0 ? config->pclk_hz : 10000000;

    esp_lcd_i80_bus_config_t bus_config = {
        .dc_gpio_num = config->rs_pin,
        .wr_gpio_num = config->wr_pin,
        .clk_src = LCD_CLK_SRC_DEFAULT,
        .data_gpio_nums = {
            config->d0_pin, config->d1_pin, config->d2_pin, config->d3_pin,
            config->d4_pin, config->d5_pin, config->d6_pin, config->d7_pin,
        },
        .bus_width = 8,
        .max_transfer_bytes = LCD_STRIP_MAX_BYTES,
        .dma_burst_size = 64,
        .sram_trans_align = 0,
    };
    ESP_ERROR_CHECK(esp_lcd_new_i80_bus(&bus_config, &handle->bus));

    esp_lcd_panel_io_i80_config_t io_config = {
        .cs_gpio_num = config->cs_pin,
        .pclk_hz = pclk_hz,
        .trans_queue_depth = 2,
        .on_color_trans_done = on_color_trans_done,
        .user_ctx = handle,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
        .dc_levels = {
            .dc_idle_level = 0,
            .dc_cmd_level = 0,
            .dc_dummy_level = 0,
            .dc_data_level = 1,
        },
        .flags = {
            .cs_active_high = 0,
            .reverse_color_bits = 0,
            .swap_color_bytes = 0,
            .pclk_active_neg = 0,
            .pclk_idle_low = 0,
        },
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_i80(handle->bus, &io_config, &handle->io));

    if (config->rst_pin >= 0) {
        gpio_config_t rst_conf = {
            .pin_bit_mask = (1ULL << config->rst_pin),
            .mode = GPIO_MODE_OUTPUT,
        };
        gpio_config(&rst_conf);
        gpio_set_level(config->rst_pin, 1);
        vTaskDelay(pdMS_TO_TICKS(10));
        gpio_set_level(config->rst_pin, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level(config->rst_pin, 1);
        vTaskDelay(pdMS_TO_TICKS(150));
    }

    if (config->rd_pin >= 0) {
        gpio_config_t rd_conf = {
            .pin_bit_mask = (1ULL << config->rd_pin),
            .mode = GPIO_MODE_OUTPUT,
        };
        gpio_config(&rd_conf);
        gpio_set_level(config->rd_pin, 1);
    }

    ESP_ERROR_CHECK(ili9486_init(handle->io, config->width, config->height, config->madctl));

    handle->initialized = true;
    ESP_LOGI(TAG, "I80 LCD+DMA initialized (%dx%d, pclk=%dHz, strip=%dKB)",
             config->width, config->height, pclk_hz, LCD_STRIP_MAX_BYTES / 1024);
    return ESP_OK;
}

esp_err_t lcd_parallel_draw_bitmap(lcd_parallel_handle_t *handle,
                                   uint16_t x, uint16_t y,
                                   uint16_t w, uint16_t h,
                                   const uint16_t *color_data)
{
    if (!handle->initialized || !handle->io) return ESP_ERR_INVALID_STATE;

    xSemaphoreTake(handle->mutex, portMAX_DELAY);

    uint32_t row_bytes = (uint32_t)w * 2;
    uint32_t max_rows_per_strip = LCD_STRIP_MAX_BYTES / row_bytes;
    if (max_rows_per_strip == 0) max_rows_per_strip = 1;

    uint16_t remaining = h;
    uint16_t cur_y = y;
    const uint8_t *ptr = (const uint8_t *)color_data;

    while (remaining > 0) {
        uint16_t strip_h = remaining > max_rows_per_strip ? max_rows_per_strip : remaining;
        uint32_t strip_bytes = (uint32_t)strip_h * row_bytes;

        lcd_set_window(handle->io, x, cur_y, x + w - 1, cur_y + strip_h - 1);

        esp_lcd_panel_io_tx_color(handle->io, ILI9486_RAMWR, ptr, strip_bytes);

        xSemaphoreTake(handle->trans_done_sem, pdMS_TO_TICKS(500));

        ptr += strip_bytes;
        cur_y += strip_h;
        remaining -= strip_h;
    }

    xSemaphoreGive(handle->mutex);
    return ESP_OK;
}

esp_err_t lcd_parallel_fill_color(lcd_parallel_handle_t *handle,
                                  uint16_t x, uint16_t y,
                                  uint16_t w, uint16_t h,
                                  uint16_t color)
{
    if (!handle->initialized || !handle->io) return ESP_ERR_INVALID_STATE;

    xSemaphoreTake(handle->mutex, portMAX_DELAY);

    uint32_t row_bytes = (uint32_t)w * 2;
    uint32_t max_rows_per_strip = LCD_STRIP_MAX_BYTES / row_bytes;
    if (max_rows_per_strip == 0) max_rows_per_strip = 1;

    uint32_t strip_pixels = (uint32_t)w * max_rows_per_strip;
    uint32_t strip_bytes = strip_pixels * 2;
    uint16_t *fill_buf = heap_caps_malloc(strip_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!fill_buf) {
        xSemaphoreGive(handle->mutex);
        return ESP_ERR_NO_MEM;
    }

    for (uint32_t i = 0; i < strip_pixels; i++) {
        fill_buf[i] = color;
    }

    uint16_t remaining = h;
    uint16_t cur_y = y;

    while (remaining > 0) {
        uint16_t strip_h = remaining > max_rows_per_strip ? max_rows_per_strip : remaining;
        uint32_t send_bytes = (uint32_t)strip_h * row_bytes;

        lcd_set_window(handle->io, x, cur_y, x + w - 1, cur_y + strip_h - 1);

        esp_lcd_panel_io_tx_color(handle->io, ILI9486_RAMWR, (const uint8_t *)fill_buf, send_bytes);

        xSemaphoreTake(handle->trans_done_sem, pdMS_TO_TICKS(500));

        cur_y += strip_h;
        remaining -= strip_h;
    }

    free(fill_buf);
    xSemaphoreGive(handle->mutex);
    return ESP_OK;
}
