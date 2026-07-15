/**
 * LuomiNest P4 - BSP LCD 句柄
 * 切片 2: 只导出句柄, 不让 app 知道引脚/初始化序列
 * 切片 9 重构: bsp_lcd 只做 LDO + DSI bus + DBI IO + DPI panel + JD9165 init +
 *              背光 + 一次性蓝屏; DSI 写权限已交给 espressif/esp_lvgl_port (LVGL 单生产者)
 */

#ifndef BSP_LCD_H
#define BSP_LCD_H

#include "esp_err.h"
#include "esp_lcd_types.h"   /* esp_lcd_panel_handle_t / esp_lcd_panel_io_handle_t */
#include "bsp_pins.h"        /* BSP_LCD_H_RES / BSP_LCD_V_RES 等 LCD 几何宏 */

esp_err_t bsp_lcd_init(void);
esp_err_t bsp_lcd_set_brightness(int percent);
esp_err_t bsp_lcd_fill_blue(void);

/** 切片 9 重构: 把 DSI 面板句柄交给 app, 由 app 创建 lvgl_port_display_dsi_cfg.
 *  分层铁律: bsp 仍不知道 LVGL, 只导出 ESP-IDF 句柄类型. */
esp_lcd_panel_handle_t bsp_lcd_get_panel_handle(void);

/** 切片 9 重构: DBI IO 句柄, 给 lvgl_port_add_disp_dsi 用来发 JD9165 init cmd. */
esp_lcd_panel_io_handle_t bsp_lcd_get_io_handle(void);

#endif /* BSP_LCD_H */
