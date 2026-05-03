#include "touch_driver.h"
#include "pin_config.h"
#include "esp_log.h"
#include "esp_lcd_touch_gt911.h"
#include "driver/i2c_master.h"

static const char *TAG = "touch";

static i2c_master_bus_handle_t s_i2c_bus = NULL;
static esp_lcd_touch_handle_t s_touch_handle = NULL;

esp_err_t touch_driver_init(lv_display_t *disp, lv_indev_t **out_indev)
{
    if (!s_i2c_bus) {
        i2c_master_bus_config_t bus_config = {
            .i2c_port = I2C_NUM_1,
            .sda_io_num = TOUCH_SDA_PIN,
            .scl_io_num = TOUCH_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .flags.enable_internal_pullup = true,
        };
        esp_err_t ret = i2c_new_master_bus(&bus_config, &s_i2c_bus);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "I2C bus init failed: %s", esp_err_to_name(ret));
            return ret;
        }
        ESP_LOGI(TAG, "I2C bus initialized (SDA=%d, SCL=%d, port=1)", TOUCH_SDA_PIN, TOUCH_SCL_PIN);
    }

    esp_lcd_panel_io_handle_t tp_io = NULL;
    esp_lcd_panel_io_i2c_config_t tp_io_config = ESP_LCD_TOUCH_IO_I2C_GT911_CONFIG();
    tp_io_config.scl_speed_hz = 400000;

    esp_err_t ret = esp_lcd_new_panel_io_i2c(s_i2c_bus, &tp_io_config, &tp_io);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Touch IO init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    esp_lcd_touch_config_t tp_config = {
        .x_max = 1024,
        .y_max = 600,
        .rst_gpio_num = TOUCH_RST_PIN,
        .int_gpio_num = TOUCH_INT_PIN,
        .levels = {
            .reset = 0,
            .interrupt = 0,
        },
        .flags = {
            .swap_xy = 0,
            .mirror_x = 0,
            .mirror_y = 0,
        },
    };

    ret = esp_lcd_touch_new_i2c_gt911(tp_io, &tp_config, &s_touch_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "GT911 init failed: %s", esp_err_to_name(ret));
        return ret;
    }
    ESP_LOGI(TAG, "GT911 touch initialized");

    const lvgl_port_touch_cfg_t touch_cfg = {
        .disp = disp,
        .handle = s_touch_handle,
    };
    lv_indev_t *indev = lvgl_port_add_touch(&touch_cfg);
    if (!indev) {
        ESP_LOGE(TAG, "Failed to add touch to LVGL");
        return ESP_FAIL;
    }

    if (out_indev) *out_indev = indev;
    ESP_LOGI(TAG, "Touch input device ready");
    return ESP_OK;
}
