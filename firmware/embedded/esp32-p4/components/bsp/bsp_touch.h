/**
 * LuomiNest P4 - BSP Touch (GT911 I2C)
 * 切片 3: 串口打印触摸坐标
 * 切片 13 重构: 导出 handle 给 LVGL indev, app_touch 任务删除
 */

#ifndef BSP_TOUCH_H
#define BSP_TOUCH_H

#include "esp_err.h"
#include "esp_lcd_touch.h"

esp_err_t bsp_touch_init(void);

/** 获取 GT911 touch handle (给 lvgl_port_add_touch 用). */
esp_lcd_touch_handle_t bsp_touch_get_handle(void);

/** 读取一次触摸坐标. 有触摸返回 ESP_OK, 无触摸返回 ESP_ERR_NOT_FOUND. */
esp_err_t bsp_touch_read(uint16_t *x, uint16_t *y);

#endif /* BSP_TOUCH_H */
