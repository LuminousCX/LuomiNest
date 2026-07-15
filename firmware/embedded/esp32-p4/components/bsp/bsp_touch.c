/**
 * LuomiNest P4 - BSP Touch (GT911 I2C)
 * 切片 3: 触摸坐标读
 *
 * 后续切片: 触摸事件通过 LVGL indev 注入, 不再用轮询读
 *           (bsp_touch.h 保留, bsp_touch.c 内部切到 LVGL 注册)
 */

#include "bsp_touch.h"
#include "bsp_pins.h"
#include "esp_log.h"
#include "esp_check.h"
#include "driver/i2c_master.h"
#include "esp_lcd_touch_gt911.h"

static const char *TAG = "bsp_touch";
static i2c_master_bus_handle_t s_i2c = NULL;
static esp_lcd_panel_io_handle_t s_io = NULL;  /* GT911 走 LCD panel IO 而非裸 I2C */
static esp_lcd_touch_handle_t s_touch = NULL;

esp_err_t bsp_touch_init(void)
{
    ESP_LOGI(TAG, "init start");

    /* 1. I2C master bus (SDA=7, SCL=8, 内部上拉) */
    i2c_master_bus_config_t i2c_cfg = {
        .i2c_port            = I2C_NUM_0,
        .sda_io_num          = BSP_TOUCH_SDA_PIN,
        .scl_io_num          = BSP_TOUCH_SCL_PIN,
        .clk_source          = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt   = 7,
        .flags.enable_internal_pullup = true,
    };
    ESP_RETURN_ON_ERROR(i2c_new_master_bus(&i2c_cfg, &s_i2c), TAG, "I2C bus");

    /* 2. LCD panel IO over I2C (GT911 走 8-bit 命令协议) */
    esp_lcd_panel_io_i2c_config_t io_i2c_cfg = {
        .dev_addr            = ESP_LCD_TOUCH_IO_I2C_GT911_ADDRESS,
        .scl_speed_hz        = 400 * 1000,
        .control_phase_bytes = 1,
        .dc_bit_offset       = 0,
        .lcd_cmd_bits        = 16,
        .flags.disable_control_phase = 1,
    };
    ESP_RETURN_ON_ERROR(esp_lcd_new_panel_io_i2c(s_i2c, &io_i2c_cfg, &s_io), TAG, "LCD IO I2C");

    /* 3. GT911 (组件内部会探测 0x5D / 0x14) */
    esp_lcd_touch_config_t touch_cfg = {
        .x_max        = BSP_LCD_H_RES,
        .y_max        = BSP_LCD_V_RES,
        .rst_gpio_num = BSP_TOUCH_RST_PIN,
        .int_gpio_num = BSP_TOUCH_INT_PIN,
        .levels = {
            .reset     = 0,
            .interrupt = 0,
        },
        .flags = {
            .swap_xy  = false,
            .mirror_x = false,
            .mirror_y = false,
        },
    };
    ESP_RETURN_ON_ERROR(esp_lcd_touch_new_i2c_gt911(s_io, &touch_cfg, &s_touch), TAG, "GT911");

    ESP_LOGI(TAG, "init ok");
    return ESP_OK;
}

esp_lcd_touch_handle_t bsp_touch_get_handle(void)
{
    return s_touch;
}

esp_err_t bsp_touch_read(uint16_t *x, uint16_t *y)
{
    if (s_touch == NULL) return ESP_ERR_INVALID_STATE;

    esp_lcd_touch_point_data_t pt = {0};
    uint8_t cnt = 0;
    ESP_RETURN_ON_ERROR(esp_lcd_touch_read_data(s_touch), TAG, "read data");
    ESP_RETURN_ON_ERROR(esp_lcd_touch_get_data(s_touch, &pt, &cnt, 1), TAG, "get data");

    if (cnt > 0) {
        *x = pt.x;
        *y = pt.y;
        return ESP_OK;
    }
    return ESP_ERR_NOT_FOUND;
}
