#ifndef SETTINGS_UI_H
#define SETTINGS_UI_H

#include "lvgl.h"
#include "esp_err.h"
#include "web_config.h"

typedef void (*settings_back_cb_t)(void);

#define WIFI_SCAN_MAX 15

typedef struct {
    lv_obj_t *page;
    lv_obj_t *form_cont;
    lv_obj_t *kb;
    lv_obj_t *kb_cont;
    lv_obj_t *ta_ssid;
    lv_obj_t *ta_pass;
    lv_obj_t *ta_broker;
    lv_obj_t *ta_client;
    lv_obj_t *status_label;
    lv_obj_t *slider_brightness;
    lv_obj_t *slider_volume;
    lv_obj_t *lbl_brightness_val;
    lv_obj_t *lbl_volume_val;
    lv_obj_t *wifi_scan_list;
    lv_obj_t *wifi_scan_btn;
    lv_obj_t *info_label;
    bool kb_visible;
    settings_back_cb_t back_cb;
} settings_ui_t;

esp_err_t settings_ui_init(settings_ui_t *s, lv_obj_t *parent, int32_t width, int32_t height);
void settings_ui_load_config(settings_ui_t *s, const ln_config_t *cfg);
void settings_ui_hide_keyboard(settings_ui_t *s);
void settings_ui_set_back_cb(settings_ui_t *s, settings_back_cb_t cb);

#endif
