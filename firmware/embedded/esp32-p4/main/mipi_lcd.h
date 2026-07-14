#ifndef MIPI_LCD_H
#define MIPI_LCD_H

#include "esp_lcd_panel_ops.h"
#include "esp_lcd_mipi_dsi.h"
#include "esp_err.h"

#define MIPI_LCD_WIDTH              1024
#define MIPI_LCD_HEIGHT             600
#define MIPI_LCD_DSI_LANE_NUM       2
#define MIPI_LCD_LANE_BITRATE_MBPS  750
#define MIPI_LCD_DPI_CLK_MHZ        52

#define MIPI_DSI_PHY_LDO_CHAN       3
#define MIPI_DSI_PHY_LDO_VOLTAGE_MV 2500

#define MIPI_LCD_RST_PIN            GPIO_NUM_0
#define MIPI_LCD_BL_PIN             GPIO_NUM_23

#define LCD_LEDC_CH                 1

typedef struct {
    esp_lcd_dsi_bus_handle_t    mipi_dsi_bus;
    esp_lcd_panel_io_handle_t   io;
    esp_lcd_panel_handle_t      dpi_panel;
    esp_lcd_panel_handle_t      control;
    int rst_pin;
    int bl_pin;
    int width;
    int height;
} mipi_lcd_handle_t;

esp_err_t mipi_lcd_init(mipi_lcd_handle_t *handle);
esp_err_t mipi_lcd_brightness_init(void);
esp_err_t mipi_lcd_brightness_set(int brightness_percent);
esp_err_t mipi_lcd_backlight_on(void);
esp_err_t mipi_lcd_backlight_off(void);

#endif
