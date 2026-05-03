#ifndef ST7735S_H
#define ST7735S_H

#include "driver/spi_master.h"
#include "esp_err.h"

typedef struct {
    spi_host_device_t spi_host;
    int clk_pin;
    int mosi_pin;
    int dc_pin;
    int rst_pin;
    int cs_pin;
    int bl_pin;
    int width;
    int height;
    int spi_freq;
    int x_offset;
    int y_offset;
} st7735s_config_t;

typedef struct {
    st7735s_config_t cfg;
    spi_device_handle_t spi_dev;
    bool initialized;
} st7735s_handle_t;

esp_err_t st7735s_init(const st7735s_config_t *config, st7735s_handle_t *handle);
esp_err_t st7735s_set_backlight(st7735s_handle_t *handle, uint8_t brightness);
esp_err_t st7735s_draw_bitmap(st7735s_handle_t *handle,
                               uint16_t x, uint16_t y,
                               uint16_t w, uint16_t h,
                               const uint16_t *color_data);
esp_err_t st7735s_fill_color(st7735s_handle_t *handle,
                              uint16_t x, uint16_t y,
                              uint16_t w, uint16_t h,
                              uint16_t color);

#endif
