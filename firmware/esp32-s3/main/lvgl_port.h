#ifndef LVGL_PORT_H
#define LVGL_PORT_H

#include "lvgl.h"
#include "st7735s.h"

typedef struct {
    st7735s_handle_t *lcd_handle;
    lv_display_t *display;
    lv_obj_t *screen;
} lvgl_port_t;

esp_err_t lvgl_port_init(st7735s_handle_t *lcd_handle, lvgl_port_t *port);
void lvgl_port_lock(void);
void lvgl_port_unlock(void);

#endif
