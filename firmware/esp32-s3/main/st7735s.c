#include "st7735s.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

static const char *TAG = "st7735s";

#define ST7735S_NOP     0x00
#define ST7735S_SWRESET 0x01
#define ST7735S_SLPIN   0x10
#define ST7735S_SLPOUT  0x11
#define ST7735S_PTLON   0x12
#define ST7735S_NORON   0x13
#define ST7735S_INVOFF  0x20
#define ST7735S_INVON   0x21
#define ST7735S_DISPOFF 0x28
#define ST7735S_DISPON  0x29
#define ST7735S_CASET   0x2A
#define ST7735S_RASET   0x2B
#define ST7735S_RAMWR   0x2C
#define ST7735S_RAMRD   0x2E
#define ST7735S_MADCTL  0x36
#define ST7735S_COLMOD  0x3A
#define ST7735S_FRMCTR1 0xB1
#define ST7735S_FRMCTR2 0xB2
#define ST7735S_FRMCTR3 0xB3
#define ST7735S_INVCTR  0xB4
#define ST7735S_PWCTR1  0xC0
#define ST7735S_PWCTR2  0xC1
#define ST7735S_PWCTR3  0xC2
#define ST7735S_PWCTR4  0xC3
#define ST7735S_PWCTR5  0xC4
#define ST7735S_VMCTR1  0xC5
#define ST7735S_GMCTRP1 0xE0
#define ST7735S_GMCTRN1 0xE1

static inline void cs_low(st7735s_handle_t *handle)
{
    if (handle->cfg.cs_pin >= 0) {
        gpio_set_level(handle->cfg.cs_pin, 0);
    }
}

static inline void cs_high(st7735s_handle_t *handle)
{
    if (handle->cfg.cs_pin >= 0) {
        gpio_set_level(handle->cfg.cs_pin, 1);
    }
}

static void st7735s_cmd(st7735s_handle_t *handle, uint8_t cmd)
{
    cs_low(handle);
    gpio_set_level(handle->cfg.dc_pin, 0);
    spi_transaction_t t = {
        .length = 8,
        .tx_buffer = &cmd,
    };
    spi_device_polling_transmit(handle->spi_dev, &t);
    cs_high(handle);
}

static void st7735s_data(st7735s_handle_t *handle, const uint8_t *data, int len)
{
    if (len == 0) return;
    cs_low(handle);
    gpio_set_level(handle->cfg.dc_pin, 1);
    spi_transaction_t t = {
        .length = len * 8,
        .tx_buffer = data,
    };
    spi_device_polling_transmit(handle->spi_dev, &t);
    cs_high(handle);
}

static void st7735s_data16(st7735s_handle_t *handle, uint16_t val)
{
    uint8_t buf[2] = { val >> 8, val & 0xFF };
    st7735s_data(handle, buf, 2);
}

static void st7735s_reset(st7735s_handle_t *handle)
{
    if (handle->cfg.rst_pin >= 0) {
        gpio_set_level(handle->cfg.rst_pin, 1);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level(handle->cfg.rst_pin, 0);
        vTaskDelay(pdMS_TO_TICKS(100));
        gpio_set_level(handle->cfg.rst_pin, 1);
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}

static void st7735s_set_window(st7735s_handle_t *handle,
                                uint16_t x0, uint16_t y0,
                                uint16_t x1, uint16_t y1)
{
    x0 += handle->cfg.x_offset;
    x1 += handle->cfg.x_offset;
    y0 += handle->cfg.y_offset;
    y1 += handle->cfg.y_offset;

    st7735s_cmd(handle, ST7735S_CASET);
    st7735s_data16(handle, x0);
    st7735s_data16(handle, x1);

    st7735s_cmd(handle, ST7735S_RASET);
    st7735s_data16(handle, y0);
    st7735s_data16(handle, y1);

    st7735s_cmd(handle, ST7735S_RAMWR);
}

esp_err_t st7735s_init(const st7735s_config_t *config, st7735s_handle_t *handle)
{
    memcpy(&handle->cfg, config, sizeof(st7735s_config_t));

    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << config->dc_pin),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);

    if (config->rst_pin >= 0) {
        io_conf.pin_bit_mask = (1ULL << config->rst_pin);
        gpio_config(&io_conf);
    }

    if (config->cs_pin >= 0) {
        io_conf.pin_bit_mask = (1ULL << config->cs_pin);
        gpio_config(&io_conf);
        gpio_set_level(config->cs_pin, 1);
    }

    if (config->bl_pin >= 0) {
        io_conf.pin_bit_mask = (1ULL << config->bl_pin);
        gpio_config(&io_conf);
        gpio_set_level(config->bl_pin, 0);
    }

    spi_bus_config_t bus_cfg = {
        .mosi_io_num = config->mosi_pin,
        .miso_io_num = -1,
        .sclk_io_num = config->clk_pin,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = config->width * config->height * 2,
    };
    ESP_ERROR_CHECK(spi_bus_initialize(config->spi_host, &bus_cfg, SPI_DMA_CH_AUTO));

    spi_device_interface_config_t dev_cfg = {
        .clock_speed_hz = config->spi_freq,
        .mode = 0,
        .spics_io_num = -1,
        .queue_size = 7,
        .flags = SPI_DEVICE_HALFDUPLEX,
    };
    ESP_ERROR_CHECK(spi_bus_add_device(config->spi_host, &dev_cfg, &handle->spi_dev));

    st7735s_reset(handle);

    st7735s_cmd(handle, ST7735S_SWRESET);
    vTaskDelay(pdMS_TO_TICKS(150));

    st7735s_cmd(handle, ST7735S_SLPOUT);
    vTaskDelay(pdMS_TO_TICKS(500));

    st7735s_cmd(handle, ST7735S_FRMCTR1);
    uint8_t frm1[] = { 0x01, 0x2C, 0x2D };
    st7735s_data(handle, frm1, 3);

    st7735s_cmd(handle, ST7735S_FRMCTR2);
    uint8_t frm2[] = { 0x01, 0x2C, 0x2D };
    st7735s_data(handle, frm2, 3);

    st7735s_cmd(handle, ST7735S_FRMCTR3);
    uint8_t frm3[] = { 0x01, 0x2C, 0x2D, 0x01, 0x2C, 0x2D };
    st7735s_data(handle, frm3, 6);

    st7735s_cmd(handle, ST7735S_INVCTR);
    uint8_t invctr[] = { 0x07 };
    st7735s_data(handle, invctr, 1);

    st7735s_cmd(handle, ST7735S_PWCTR1);
    uint8_t pw1[] = { 0xA2, 0x02, 0x84 };
    st7735s_data(handle, pw1, 3);

    st7735s_cmd(handle, ST7735S_PWCTR2);
    uint8_t pw2[] = { 0xC5 };
    st7735s_data(handle, pw2, 1);

    st7735s_cmd(handle, ST7735S_PWCTR3);
    uint8_t pw3[] = { 0x0A, 0x00 };
    st7735s_data(handle, pw3, 2);

    st7735s_cmd(handle, ST7735S_PWCTR4);
    uint8_t pw4[] = { 0x8A, 0x2A };
    st7735s_data(handle, pw4, 2);

    st7735s_cmd(handle, ST7735S_PWCTR5);
    uint8_t pw5[] = { 0x8A, 0xEE };
    st7735s_data(handle, pw5, 2);

    st7735s_cmd(handle, ST7735S_VMCTR1);
    uint8_t vm1[] = { 0x0E };
    st7735s_data(handle, vm1, 1);

    st7735s_cmd(handle, ST7735S_INVOFF);

    st7735s_cmd(handle, ST7735S_MADCTL);
    uint8_t madctl[] = { 0x00 };
    st7735s_data(handle, madctl, 1);

    st7735s_cmd(handle, ST7735S_COLMOD);
    uint8_t colmod[] = { 0x05 };
    st7735s_data(handle, colmod, 1);

    st7735s_cmd(handle, ST7735S_GMCTRP1);
    uint8_t gmp[] = { 0x02, 0x1c, 0x07, 0x12, 0x37, 0x32, 0x29, 0x2d,
                      0x29, 0x25, 0x2B, 0x39, 0x00, 0x01, 0x03, 0x10 };
    st7735s_data(handle, gmp, 16);

    st7735s_cmd(handle, ST7735S_GMCTRN1);
    uint8_t gmn[] = { 0x03, 0x1d, 0x07, 0x06, 0x2E, 0x2C, 0x29, 0x2D,
                      0x2E, 0x2E, 0x37, 0x3F, 0x00, 0x00, 0x02, 0x10 };
    st7735s_data(handle, gmn, 16);

    st7735s_cmd(handle, ST7735S_NORON);
    vTaskDelay(pdMS_TO_TICKS(10));

    st7735s_cmd(handle, ST7735S_DISPON);
    vTaskDelay(pdMS_TO_TICKS(100));

    if (config->bl_pin >= 0) {
        gpio_set_level(config->bl_pin, 1);
    }

    handle->initialized = true;
    ESP_LOGI(TAG, "ST7735S initialized (%dx%d, offset=%d,%d, SPI=%dHz)",
             config->width, config->height, config->x_offset, config->y_offset, config->spi_freq);
    return ESP_OK;
}

esp_err_t st7735s_set_backlight(st7735s_handle_t *handle, uint8_t brightness)
{
    if (handle->cfg.bl_pin < 0) return ESP_ERR_NOT_SUPPORTED;
    if (brightness > 0) {
        gpio_set_level(handle->cfg.bl_pin, 1);
    } else {
        gpio_set_level(handle->cfg.bl_pin, 0);
    }
    return ESP_OK;
}

esp_err_t st7735s_draw_bitmap(st7735s_handle_t *handle,
                               uint16_t x, uint16_t y,
                               uint16_t w, uint16_t h,
                               const uint16_t *color_data)
{
    if (!handle->initialized) return ESP_ERR_INVALID_STATE;

    uint32_t total_bytes = (uint32_t)w * h * 2;

    st7735s_set_window(handle, x, y, x + w - 1, y + h - 1);

    cs_low(handle);
    gpio_set_level(handle->cfg.dc_pin, 1);

    spi_transaction_t t = {
        .length = total_bytes * 8,
        .tx_buffer = color_data,
    };
    spi_device_polling_transmit(handle->spi_dev, &t);

    cs_high(handle);
    return ESP_OK;
}

esp_err_t st7735s_fill_color(st7735s_handle_t *handle,
                              uint16_t x, uint16_t y,
                              uint16_t w, uint16_t h,
                              uint16_t color)
{
    if (!handle->initialized) return ESP_ERR_INVALID_STATE;

    st7735s_set_window(handle, x, y, x + w - 1, y + h - 1);

    uint16_t *line_buf = heap_caps_malloc(w * 2, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    if (!line_buf) {
        ESP_LOGE(TAG, "Failed to allocate line buffer (%d bytes)", w * 2);
        return ESP_ERR_NO_MEM;
    }

    uint16_t swapped = __builtin_bswap16(color);
    for (int i = 0; i < w; i++) {
        line_buf[i] = swapped;
    }

    cs_low(handle);
    gpio_set_level(handle->cfg.dc_pin, 1);

    uint32_t line_bytes = w * 2;
    for (uint16_t row = 0; row < h; row++) {
        spi_transaction_t t = {
            .length = line_bytes * 8,
            .tx_buffer = line_buf,
        };
        spi_device_polling_transmit(handle->spi_dev, &t);
    }

    cs_high(handle);
    free(line_buf);
    return ESP_OK;
}
