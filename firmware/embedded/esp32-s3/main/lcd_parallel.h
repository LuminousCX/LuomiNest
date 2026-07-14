#ifndef LCD_PARALLEL_H
#define LCD_PARALLEL_H

#include "esp_err.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_io_i80.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int rst_pin;
    int cs_pin;
    int rs_pin;
    int wr_pin;
    int rd_pin;
    int d0_pin;
    int d1_pin;
    int d2_pin;
    int d3_pin;
    int d4_pin;
    int d5_pin;
    int d6_pin;
    int d7_pin;
    int width;
    int height;
    uint8_t madctl;
    int pclk_hz;
} lcd_parallel_config_t;

typedef struct {
    lcd_parallel_config_t cfg;
    esp_lcd_i80_bus_handle_t bus;
    esp_lcd_panel_io_handle_t io;
    SemaphoreHandle_t trans_done_sem;
    SemaphoreHandle_t mutex;
    bool initialized;
} lcd_parallel_handle_t;

esp_err_t lcd_parallel_init(const lcd_parallel_config_t *config, lcd_parallel_handle_t *handle);
esp_err_t lcd_parallel_draw_bitmap(lcd_parallel_handle_t *handle,
                                   uint16_t x, uint16_t y,
                                   uint16_t w, uint16_t h,
                                   const uint16_t *color_data);
esp_err_t lcd_parallel_fill_color(lcd_parallel_handle_t *handle,
                                  uint16_t x, uint16_t y,
                                  uint16_t w, uint16_t h,
                                  uint16_t color);

static inline void lcd_parallel_lock(lcd_parallel_handle_t *handle)
{
    if (handle && handle->mutex) {
        xSemaphoreTake(handle->mutex, portMAX_DELAY);
    }
}

static inline void lcd_parallel_unlock(lcd_parallel_handle_t *handle)
{
    if (handle && handle->mutex) {
        xSemaphoreGive(handle->mutex);
    }
}

#endif
