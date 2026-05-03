#ifndef TOUCH_DRIVER_H
#define TOUCH_DRIVER_H

#include "esp_lcd_touch.h"
#include "esp_lvgl_port.h"
#include "lvgl.h"

esp_err_t touch_driver_init(lv_display_t *disp, lv_indev_t **out_indev);

#endif
