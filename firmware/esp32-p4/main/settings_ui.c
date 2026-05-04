#include "settings_ui.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "esp_wifi.h"
#include "esp_chip_info.h"
#include "mipi_lcd.h"
#include <string.h>

static const char *TAG = "settings_ui";

#define COLOR_PAGE_BG      lv_color_hex(0x0F0F1A)
#define COLOR_HEADER_BG    lv_color_hex(0x161628)
#define COLOR_SECTION_BG   lv_color_hex(0x161628)
#define COLOR_TA_BG        lv_color_hex(0x1E1E32)
#define COLOR_TA_BORDER    lv_color_hex(0x2A2A4A)
#define COLOR_TA_FOCUS     lv_color_hex(0x4A6A8A)
#define COLOR_BTN_BG       lv_color_hex(0x1A4A5A)
#define COLOR_BTN_PRESS    lv_color_hex(0x2A6A7A)
#define COLOR_BTN_DANGER   lv_color_hex(0x5A2A2A)
#define COLOR_TEXT_PRI     lv_color_hex(0xC8C8E0)
#define COLOR_TEXT_SEC     lv_color_hex(0x7878A0)
#define COLOR_ACCENT       lv_color_hex(0x4ECDC4)
#define COLOR_KB_BG        lv_color_hex(0x12122A)
#define COLOR_KB_BTN       lv_color_hex(0x2A2A4A)
#define COLOR_KB_SPEC      lv_color_hex(0x1A3A4A)
#define COLOR_STATUS_OK    lv_color_hex(0x4ECDC4)
#define COLOR_STATUS_ERR   lv_color_hex(0xFF6B6B)
#define COLOR_SLIDER_BG    lv_color_hex(0x1E1E32)
#define COLOR_SLIDER_IND   lv_color_hex(0x4ECDC4)
#define COLOR_SLIDER_KNOB  lv_color_hex(0x6EECD4)
#define COLOR_SCAN_ITEM    lv_color_hex(0x1E1E32)
#define COLOR_SCAN_SEL     lv_color_hex(0x2A4A5A)

#define HEADER_H           52
#define KB_HEIGHT          200
#define SECTION_RADIUS     12
#define TA_HEIGHT          48
#define PAD_PAGE           20
#define PAD_SECTION        16
#define FORM_GAP           14
#define SLIDER_H           10
#define SLIDER_KNOB        20

static settings_ui_t *s_settings_ptr = NULL;

static void wifi_item_click_cb(lv_event_t *e);

static void ta_focus_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);
    lv_obj_t *ta = lv_event_get_target(e);
    if (!s->kb_visible) {
        lv_obj_clear_flag(s->kb_cont, LV_OBJ_FLAG_HIDDEN);
        lv_obj_set_height(s->kb_cont, KB_HEIGHT);
        s->kb_visible = true;
    }
    lv_keyboard_set_textarea(s->kb, ta);
}

static void ta_ready_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);
    settings_ui_hide_keyboard(s);
}

static void kb_close_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);
    settings_ui_hide_keyboard(s);
}

static void back_btn_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);
    settings_ui_hide_keyboard(s);
    if (s->back_cb) s->back_cb();
}

static lv_obj_t *create_textarea(lv_obj_t *parent, settings_ui_t *s,
                                  const char *placeholder, int32_t max_w,
                                  bool password, int32_t max_len)
{
    lv_obj_t *ta = lv_textarea_create(parent);
    lv_obj_remove_style_all(ta);
    lv_obj_set_size(ta, max_w, TA_HEIGHT);
    lv_obj_set_style_bg_color(ta, COLOR_TA_BG, 0);
    lv_obj_set_style_bg_opa(ta, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(ta, COLOR_TA_BORDER, 0);
    lv_obj_set_style_border_width(ta, 1, 0);
    lv_obj_set_style_radius(ta, 8, 0);
    lv_obj_set_style_pad_hor(ta, 12, 0);
    lv_obj_set_style_text_color(ta, COLOR_TEXT_PRI, 0);
    lv_obj_set_style_text_font(ta, &lv_font_montserrat_16, 0);

    lv_textarea_set_one_line(ta, true);
    lv_textarea_set_placeholder_text(ta, placeholder);
    if (password) lv_textarea_set_password_mode(ta, true);
    if (max_len > 0) lv_textarea_set_max_length(ta, max_len);

    lv_obj_add_event_cb(ta, ta_focus_cb, LV_EVENT_FOCUSED, s);
    lv_obj_add_event_cb(ta, ta_ready_cb, LV_EVENT_READY, s);

    static lv_style_t style_focus;
    static bool focus_style_init = false;
    if (!focus_style_init) {
        focus_style_init = true;
        lv_style_init(&style_focus);
        lv_style_set_border_color(&style_focus, COLOR_TA_FOCUS);
        lv_style_set_border_width(&style_focus, 2);
    }
    lv_obj_add_style(ta, &style_focus, LV_STATE_FOCUSED);

    return ta;
}

static void save_btn_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);

    ln_config_t cfg = {0};
    web_config_load(&cfg);

    const char *ssid = lv_textarea_get_text(s->ta_ssid);
    const char *pass = lv_textarea_get_text(s->ta_pass);
    const char *broker = lv_textarea_get_text(s->ta_broker);
    const char *client = lv_textarea_get_text(s->ta_client);

    if (ssid && strlen(ssid) > 0) {
        strncpy(cfg.wifi_ssid, ssid, LN_MAX_SSID_LEN - 1);
        cfg.wifi_ssid[LN_MAX_SSID_LEN - 1] = '\0';
    }
    if (pass && strlen(pass) > 0) {
        strncpy(cfg.wifi_pass, pass, LN_MAX_PASS_LEN - 1);
        cfg.wifi_pass[LN_MAX_PASS_LEN - 1] = '\0';
    }
    if (broker && strlen(broker) > 0) {
        strncpy(cfg.mqtt_broker, broker, LN_MAX_BROKER_LEN - 1);
        cfg.mqtt_broker[LN_MAX_BROKER_LEN - 1] = '\0';
    }
    if (client && strlen(client) > 0) {
        strncpy(cfg.mqtt_client, client, LN_MAX_CLIENT_LEN - 1);
        cfg.mqtt_client[LN_MAX_CLIENT_LEN - 1] = '\0';
    }

    cfg.brightness = lv_slider_get_value(s->slider_brightness);
    cfg.volume = lv_slider_get_value(s->slider_volume);

    mipi_lcd_brightness_set(cfg.brightness);

    esp_err_t ret = web_config_save(&cfg);
    if (ret == ESP_OK) {
        lv_label_set_text(s->status_label, "Saved! Restarting...");
        lv_obj_set_style_text_color(s->status_label, COLOR_STATUS_OK, 0);
        vTaskDelay(pdMS_TO_TICKS(1500));
        esp_restart();
    } else {
        lv_label_set_text(s->status_label, "Save failed!");
        lv_obj_set_style_text_color(s->status_label, COLOR_STATUS_ERR, 0);
    }
}

static lv_obj_t *create_section(lv_obj_t *parent, const char *title, int32_t width)
{
    lv_obj_t *sec = lv_obj_create(parent);
    lv_obj_remove_style_all(sec);
    lv_obj_set_size(sec, width, LV_SIZE_CONTENT);
    lv_obj_set_style_bg_color(sec, COLOR_SECTION_BG, 0);
    lv_obj_set_style_bg_opa(sec, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(sec, SECTION_RADIUS, 0);
    lv_obj_set_style_pad_all(sec, PAD_SECTION, 0);
    lv_obj_set_flex_flow(sec, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(sec, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_row(sec, FORM_GAP, 0);
    lv_obj_clear_flag(sec, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl = lv_label_create(sec);
    lv_label_set_text(lbl, title);
    lv_obj_set_style_text_color(lbl, COLOR_ACCENT, 0);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_16, 0);

    return sec;
}

static lv_obj_t *create_field(lv_obj_t *parent, const char *label_text,
                               settings_ui_t *s, const char *placeholder,
                               int32_t ta_width, bool password, int32_t max_len)
{
    lv_obj_t *field = lv_obj_create(parent);
    lv_obj_remove_style_all(field);
    lv_obj_set_size(field, lv_pct(100), LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(field, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(field, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_row(field, 6, 0);
    lv_obj_clear_flag(field, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl = lv_label_create(field);
    lv_label_set_text(lbl, label_text);
    lv_obj_set_style_text_color(lbl, COLOR_TEXT_SEC, 0);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_16, 0);

    lv_obj_t *ta = create_textarea(field, s, placeholder, ta_width, password, max_len);
    return ta;
}

static lv_obj_t *create_slider_row(lv_obj_t *parent, const char *label_text,
                                    const char *symbol, int32_t width,
                                    lv_obj_t **out_slider, lv_obj_t **out_val_label)
{
    lv_obj_t *row = lv_obj_create(parent);
    lv_obj_remove_style_all(row);
    lv_obj_set_size(row, lv_pct(100), LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(row, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(row, 6, 0);
    lv_obj_clear_flag(row, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *header = lv_obj_create(row);
    lv_obj_remove_style_all(header);
    lv_obj_set_size(header, lv_pct(100), LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(header, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(header, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_clear_flag(header, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *lbl = lv_label_create(header);
    char sym_buf[16];
    snprintf(sym_buf, sizeof(sym_buf), "%s  ", symbol);
    lv_label_set_text(lbl, sym_buf);
    lv_obj_set_style_text_color(lbl, COLOR_ACCENT, 0);
    lv_obj_set_style_text_font(lbl, &lv_font_montserrat_16, 0);

    lv_obj_t *name_lbl = lv_label_create(header);
    lv_label_set_text(name_lbl, label_text);
    lv_obj_set_style_text_color(name_lbl, COLOR_TEXT_SEC, 0);
    lv_obj_set_style_text_font(name_lbl, &lv_font_montserrat_16, 0);

    lv_obj_t *spacer = lv_obj_create(header);
    lv_obj_remove_style_all(spacer);
    lv_obj_set_flex_grow(spacer, 1);
    lv_obj_set_size(spacer, 0, 0);

    lv_obj_t *val_lbl = lv_label_create(header);
    lv_label_set_text(val_lbl, "50%");
    lv_obj_set_style_text_color(val_lbl, COLOR_TEXT_PRI, 0);
    lv_obj_set_style_text_font(val_lbl, &lv_font_montserrat_16, 0);

    lv_obj_t *slider = lv_slider_create(row);
    lv_obj_set_size(slider, width, SLIDER_H);
    lv_slider_set_range(slider, 0, 100);
    lv_slider_set_value(slider, 50, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(slider, COLOR_SLIDER_BG, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(slider, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_radius(slider, 5, LV_PART_MAIN);
    lv_obj_set_style_bg_color(slider, COLOR_SLIDER_IND, LV_PART_INDICATOR);
    lv_obj_set_style_bg_opa(slider, LV_OPA_COVER, LV_PART_INDICATOR);
    lv_obj_set_style_radius(slider, 5, LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(slider, COLOR_SLIDER_KNOB, LV_PART_KNOB);
    lv_obj_set_style_bg_opa(slider, LV_OPA_COVER, LV_PART_KNOB);
    lv_obj_set_style_radius(slider, SLIDER_KNOB / 2, LV_PART_KNOB);
    lv_obj_set_style_width(slider, SLIDER_KNOB, LV_PART_KNOB);
    lv_obj_set_style_height(slider, SLIDER_KNOB, LV_PART_KNOB);

    if (out_slider) *out_slider = slider;
    if (out_val_label) *out_val_label = val_lbl;

    return row;
}

static void brightness_slider_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);
    int val = lv_slider_get_value(s->slider_brightness);
    char buf[8];
    snprintf(buf, sizeof(buf), "%d%%", val);
    lv_label_set_text(s->lbl_brightness_val, buf);
    mipi_lcd_brightness_set(val);
}

static void volume_slider_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);
    int val = lv_slider_get_value(s->slider_volume);
    char buf[8];
    snprintf(buf, sizeof(buf), "%d%%", val);
    lv_label_set_text(s->lbl_volume_val, buf);
}

static void wifi_scan_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);
    settings_ui_hide_keyboard(s);

    lv_label_set_text(s->status_label, "Scanning...");
    lv_obj_set_style_text_color(s->status_label, COLOR_ACCENT, 0);

    lv_obj_clean(s->wifi_scan_list);

    wifi_scan_config_t scan_conf = {0};
    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_start();
    esp_err_t ret = esp_wifi_scan_start(&scan_conf, true);
    if (ret != ESP_OK) {
        lv_label_set_text(s->status_label, "Scan failed");
        lv_obj_set_style_text_color(s->status_label, COLOR_STATUS_ERR, 0);
        return;
    }

    uint16_t ap_count = 0;
    esp_wifi_scan_get_ap_num(&ap_count);
    if (ap_count > WIFI_SCAN_MAX) ap_count = WIFI_SCAN_MAX;
    wifi_ap_record_t aps[WIFI_SCAN_MAX];
    esp_wifi_scan_get_ap_records(&ap_count, aps);

    for (int i = 0; i < ap_count; i++) {
        lv_obj_t *item = lv_btn_create(s->wifi_scan_list);
        lv_obj_set_size(item, lv_pct(100), 44);
        lv_obj_set_style_bg_color(item, COLOR_SCAN_ITEM, 0);
        lv_obj_set_style_bg_opa(item, LV_OPA_COVER, 0);
        lv_obj_set_style_radius(item, 8, 0);
        lv_obj_set_style_border_width(item, 0, 0);
        lv_obj_set_style_pad_hor(item, 12, 0);
        lv_obj_set_style_pad_ver(item, 6, 0);
        lv_obj_set_flex_flow(item, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(item, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

        static lv_style_t style_item_pr;
        static bool item_pr_init = false;
        if (!item_pr_init) {
            item_pr_init = true;
            lv_style_init(&style_item_pr);
            lv_style_set_bg_color(&style_item_pr, COLOR_SCAN_SEL);
        }
        lv_obj_add_style(item, &style_item_pr, LV_STATE_PRESSED);

        lv_obj_t *name = lv_label_create(item);
        char name_buf[40];
        snprintf(name_buf, sizeof(name_buf), "%s", aps[i].ssid);
        lv_label_set_text(name, name_buf);
        lv_obj_set_style_text_color(name, COLOR_TEXT_PRI, 0);
        lv_obj_set_style_text_font(name, &lv_font_montserrat_16, 0);
        lv_obj_set_flex_grow(name, 1);

        lv_obj_t *rssi_lbl = lv_label_create(item);
        char rssi_buf[16];
        snprintf(rssi_buf, sizeof(rssi_buf), "%ddBm", aps[i].rssi);
        lv_label_set_text(rssi_lbl, rssi_buf);
        lv_obj_set_style_text_color(rssi_lbl, COLOR_TEXT_SEC, 0);
        lv_obj_set_style_text_font(rssi_lbl, &lv_font_montserrat_14, 0);

        if (aps[i].authmode != WIFI_AUTH_OPEN) {
            lv_obj_t *lock = lv_label_create(item);
            lv_label_set_text(lock, "*");
            lv_obj_set_style_text_color(lock, COLOR_TEXT_SEC, 0);
            lv_obj_set_style_text_font(lock, &lv_font_montserrat_14, 0);
        }

        lv_obj_add_event_cb(item, wifi_item_click_cb, LV_EVENT_CLICKED, s);
    }

    char status_buf[32];
    snprintf(status_buf, sizeof(status_buf), "Found %d networks", ap_count);
    lv_label_set_text(s->status_label, status_buf);
    lv_obj_set_style_text_color(s->status_label, COLOR_STATUS_OK, 0);
}

static void wifi_item_click_cb(lv_event_t *e)
{
    settings_ui_t *s = (settings_ui_t *)lv_event_get_user_data(e);
    lv_obj_t *item = lv_event_get_target(e);

    uint32_t child_cnt = lv_obj_get_child_count(s->wifi_scan_list);
    for (uint32_t i = 0; i < child_cnt; i++) {
        lv_obj_t *c = lv_obj_get_child(s->wifi_scan_list, i);
        lv_obj_set_style_bg_color(c, COLOR_SCAN_ITEM, 0);
    }
    lv_obj_set_style_bg_color(item, COLOR_SCAN_SEL, 0);

    lv_obj_t *name_lbl = lv_obj_get_child(item, 0);
    if (name_lbl) {
        const char *ssid = lv_label_get_text(name_lbl);
        if (ssid && s->ta_ssid) {
            lv_textarea_set_text(s->ta_ssid, ssid);
        }
    }
}

esp_err_t settings_ui_init(settings_ui_t *s, lv_obj_t *parent, int32_t width, int32_t height)
{
    if (!s || !parent) return ESP_ERR_INVALID_ARG;

    memset(s, 0, sizeof(settings_ui_t));
    s_settings_ptr = s;

    s->page = lv_obj_create(parent);
    lv_obj_remove_style_all(s->page);
    lv_obj_set_size(s->page, width, height);
    lv_obj_set_style_bg_color(s->page, COLOR_PAGE_BG, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(s->page, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_flex_flow(s->page, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(s->page, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);
    lv_obj_clear_flag(s->page, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *header = lv_obj_create(s->page);
    lv_obj_remove_style_all(header);
    lv_obj_set_size(header, lv_pct(100), HEADER_H);
    lv_obj_set_style_bg_color(header, COLOR_HEADER_BG, 0);
    lv_obj_set_style_bg_opa(header, LV_OPA_COVER, 0);
    lv_obj_set_style_pad_left(header, 16, 0);
    lv_obj_set_style_pad_right(header, 16, 0);
    lv_obj_set_flex_flow(header, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(header, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_clear_flag(header, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *back_btn = lv_btn_create(header);
    lv_obj_set_size(back_btn, 40, 40);
    lv_obj_set_style_bg_color(back_btn, COLOR_KB_BTN, 0);
    lv_obj_set_style_bg_opa(back_btn, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(back_btn, 8, 0);
    lv_obj_set_style_border_width(back_btn, 0, 0);
    lv_obj_add_event_cb(back_btn, back_btn_cb, LV_EVENT_CLICKED, s);
    lv_obj_t *back_lbl = lv_label_create(back_btn);
    lv_label_set_text(back_lbl, LV_SYMBOL_LEFT);
    lv_obj_set_style_text_color(back_lbl, COLOR_TEXT_PRI, 0);
    lv_obj_set_style_text_font(back_lbl, &lv_font_montserrat_16, 0);
    lv_obj_center(back_lbl);

    lv_obj_t *title = lv_label_create(header);
    lv_label_set_text(title, "  " LV_SYMBOL_SETTINGS " Settings");
    lv_obj_set_style_text_color(title, COLOR_TEXT_PRI, 0);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_16, 0);

    lv_obj_t *spacer_h = lv_obj_create(header);
    lv_obj_remove_style_all(spacer_h);
    lv_obj_set_flex_grow(spacer_h, 1);
    lv_obj_set_size(spacer_h, 0, 0);

    s->form_cont = lv_obj_create(s->page);
    lv_obj_remove_style_all(s->form_cont);
    lv_obj_set_size(s->form_cont, lv_pct(100), LV_SIZE_CONTENT);
    lv_obj_set_style_pad_all(s->form_cont, PAD_PAGE, 0);
    lv_obj_set_flex_flow(s->form_cont, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_flex_align(s->form_cont, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_START);
    lv_obj_set_style_pad_row(s->form_cont, FORM_GAP, 0);
    lv_obj_set_scrollbar_mode(s->form_cont, LV_SCROLLBAR_MODE_OFF);
    lv_obj_set_scroll_dir(s->form_cont, LV_DIR_VER);
    lv_obj_set_flex_grow(s->form_cont, 1);

    int32_t sec_w = width - PAD_PAGE * 2;
    int32_t ta_width = sec_w - PAD_SECTION * 2;
    int32_t slider_w = sec_w - PAD_SECTION * 2;

    lv_obj_t *disp_sec = create_section(s->form_cont, LV_SYMBOL_IMAGE "  Display & Audio", sec_w);
    create_slider_row(disp_sec, "Brightness", LV_SYMBOL_IMAGE, slider_w,
                      &s->slider_brightness, &s->lbl_brightness_val);
    lv_slider_set_value(s->slider_brightness, 80, LV_ANIM_OFF);
    lv_label_set_text(s->lbl_brightness_val, "80%");
    lv_obj_add_event_cb(s->slider_brightness, brightness_slider_cb, LV_EVENT_VALUE_CHANGED, s);

    create_slider_row(disp_sec, "Volume", LV_SYMBOL_VOLUME_MAX, slider_w,
                      &s->slider_volume, &s->lbl_volume_val);
    lv_slider_set_value(s->slider_volume, 50, LV_ANIM_OFF);
    lv_obj_add_event_cb(s->slider_volume, volume_slider_cb, LV_EVENT_VALUE_CHANGED, s);

    lv_obj_t *wifi_sec = create_section(s->form_cont, LV_SYMBOL_WIFI "  WiFi", sec_w);

    lv_obj_t *scan_row = lv_obj_create(wifi_sec);
    lv_obj_remove_style_all(scan_row);
    lv_obj_set_size(scan_row, lv_pct(100), LV_SIZE_CONTENT);
    lv_obj_set_flex_flow(scan_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(scan_row, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(scan_row, 8, 0);
    lv_obj_clear_flag(scan_row, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *scan_lbl = lv_label_create(scan_row);
    lv_label_set_text(scan_lbl, "Available Networks");
    lv_obj_set_style_text_color(scan_lbl, COLOR_TEXT_SEC, 0);
    lv_obj_set_style_text_font(scan_lbl, &lv_font_montserrat_16, 0);

    lv_obj_t *scan_spacer = lv_obj_create(scan_row);
    lv_obj_remove_style_all(scan_spacer);
    lv_obj_set_flex_grow(scan_spacer, 1);
    lv_obj_set_size(scan_spacer, 0, 0);

    s->wifi_scan_btn = lv_btn_create(scan_row);
    lv_obj_set_size(s->wifi_scan_btn, 80, 32);
    lv_obj_set_style_bg_color(s->wifi_scan_btn, COLOR_BTN_BG, 0);
    lv_obj_set_style_bg_opa(s->wifi_scan_btn, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(s->wifi_scan_btn, 6, 0);
    lv_obj_set_style_border_width(s->wifi_scan_btn, 0, 0);
    lv_obj_add_event_cb(s->wifi_scan_btn, wifi_scan_cb, LV_EVENT_CLICKED, s);
    lv_obj_t *scan_btn_lbl = lv_label_create(s->wifi_scan_btn);
    lv_label_set_text(scan_btn_lbl, LV_SYMBOL_REFRESH " Scan");
    lv_obj_set_style_text_color(scan_btn_lbl, COLOR_TEXT_PRI, 0);
    lv_obj_set_style_text_font(scan_btn_lbl, &lv_font_montserrat_14, 0);
    lv_obj_center(scan_btn_lbl);

    s->wifi_scan_list = lv_obj_create(wifi_sec);
    lv_obj_remove_style_all(s->wifi_scan_list);
    lv_obj_set_size(s->wifi_scan_list, lv_pct(100), LV_SIZE_CONTENT);
    lv_obj_set_style_max_height(s->wifi_scan_list, 180, 0);
    lv_obj_set_flex_flow(s->wifi_scan_list, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(s->wifi_scan_list, 4, 0);
    lv_obj_set_scrollbar_mode(s->wifi_scan_list, LV_SCROLLBAR_MODE_ACTIVE);
    lv_obj_set_scroll_dir(s->wifi_scan_list, LV_DIR_VER);
    lv_obj_clear_flag(s->wifi_scan_list, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_opa(s->wifi_scan_list, LV_OPA_TRANSP, 0);

    s->ta_ssid = create_field(wifi_sec, "Network Name (SSID)", s,
                              "Enter WiFi SSID", ta_width, false, LN_MAX_SSID_LEN - 1);
    s->ta_pass = create_field(wifi_sec, "Password", s,
                              "Enter WiFi password", ta_width, true, LN_MAX_PASS_LEN - 1);

    lv_obj_t *mqtt_sec = create_section(s->form_cont, LV_SYMBOL_BELL "  MQTT Server", sec_w);
    s->ta_broker = create_field(mqtt_sec, "Broker URL", s,
                                "mqtt://192.168.1.222:1883", ta_width, false, LN_MAX_BROKER_LEN - 1);
    s->ta_client = create_field(mqtt_sec, "Client ID", s,
                                "luominest_p4_01", ta_width, false, LN_MAX_CLIENT_LEN - 1);

    lv_obj_t *info_sec = create_section(s->form_cont, LV_SYMBOL_LIST "  System Info", sec_w);
    s->info_label = lv_label_create(info_sec);
    lv_label_set_text(s->info_label, "");
    lv_obj_set_style_text_color(s->info_label, COLOR_TEXT_SEC, 0);
    lv_obj_set_style_text_font(s->info_label, &lv_font_montserrat_14, 0);

    esp_chip_info_t chip;
    esp_chip_info(&chip);
    uint32_t free_heap = esp_get_free_heap_size();
    uint32_t free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    char info_buf[256];
    snprintf(info_buf, sizeof(info_buf),
             "Chip: ESP32-P4  Cores: %d  Rev: %d\n"
             "Firmware: v0.3.0  IDF: v5.5.3\n"
             "Heap: %u KB  PSRAM: %u KB",
             chip.cores, chip.revision,
             (unsigned)(free_heap / 1024), (unsigned)(free_psram / 1024));
    lv_label_set_text(s->info_label, info_buf);

    lv_obj_t *btn_cont = lv_obj_create(s->form_cont);
    lv_obj_remove_style_all(btn_cont);
    lv_obj_set_size(btn_cont, sec_w, LV_SIZE_CONTENT);
    lv_obj_clear_flag(btn_cont, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *save_btn = lv_btn_create(btn_cont);
    lv_obj_set_size(save_btn, lv_pct(100), 48);
    lv_obj_set_style_bg_color(save_btn, COLOR_BTN_BG, 0);
    lv_obj_set_style_bg_opa(save_btn, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(save_btn, 10, 0);
    lv_obj_set_style_border_width(save_btn, 0, 0);
    lv_obj_add_event_cb(save_btn, save_btn_cb, LV_EVENT_CLICKED, s);

    static lv_style_t style_btn_pr;
    static bool btn_pr_init = false;
    if (!btn_pr_init) {
        btn_pr_init = true;
        lv_style_init(&style_btn_pr);
        lv_style_set_bg_color(&style_btn_pr, COLOR_BTN_PRESS);
    }
    lv_obj_add_style(save_btn, &style_btn_pr, LV_STATE_PRESSED);

    lv_obj_t *btn_lbl = lv_label_create(save_btn);
    lv_label_set_text(btn_lbl, LV_SYMBOL_SAVE "  Save & Restart");
    lv_obj_set_style_text_color(btn_lbl, COLOR_TEXT_PRI, 0);
    lv_obj_set_style_text_font(btn_lbl, &lv_font_montserrat_16, 0);
    lv_obj_center(btn_lbl);

    s->status_label = lv_label_create(s->form_cont);
    lv_label_set_text(s->status_label, "");
    lv_obj_set_style_text_font(s->status_label, &lv_font_montserrat_16, 0);
    lv_obj_set_style_text_color(s->status_label, COLOR_STATUS_OK, 0);

    s->kb_cont = lv_obj_create(s->page);
    lv_obj_remove_style_all(s->kb_cont);
    lv_obj_set_size(s->kb_cont, lv_pct(100), 0);
    lv_obj_set_style_bg_color(s->kb_cont, COLOR_KB_BG, 0);
    lv_obj_set_style_bg_opa(s->kb_cont, LV_OPA_COVER, 0);
    lv_obj_add_flag(s->kb_cont, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(s->kb_cont, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *kb_close = lv_btn_create(s->kb_cont);
    lv_obj_set_size(kb_close, 70, 28);
    lv_obj_align(kb_close, LV_ALIGN_TOP_RIGHT, -4, 2);
    lv_obj_set_style_bg_color(kb_close, COLOR_KB_SPEC, 0);
    lv_obj_set_style_bg_opa(kb_close, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(kb_close, 4, 0);
    lv_obj_set_style_border_width(kb_close, 0, 0);
    lv_obj_add_event_cb(kb_close, kb_close_cb, LV_EVENT_CLICKED, s);

    lv_obj_t *kb_close_lbl = lv_label_create(kb_close);
    lv_label_set_text(kb_close_lbl, "Close");
    lv_obj_set_style_text_color(kb_close_lbl, COLOR_TEXT_SEC, 0);
    lv_obj_set_style_text_font(kb_close_lbl, &lv_font_montserrat_14, 0);
    lv_obj_center(kb_close_lbl);

    s->kb = lv_keyboard_create(s->kb_cont);
    lv_obj_set_size(s->kb, lv_pct(100), KB_HEIGHT - 32);
    lv_obj_align(s->kb, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_set_style_bg_color(s->kb, COLOR_KB_BG, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(s->kb, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_bg_color(s->kb, COLOR_KB_BTN, LV_PART_ITEMS);
    lv_obj_set_style_bg_opa(s->kb, LV_OPA_COVER, LV_PART_ITEMS);
    lv_obj_set_style_text_color(s->kb, COLOR_TEXT_PRI, LV_PART_ITEMS);
    lv_obj_set_style_text_font(s->kb, &lv_font_montserrat_14, LV_PART_ITEMS);
    lv_obj_set_style_radius(s->kb, 6, LV_PART_ITEMS);
    lv_obj_set_style_border_width(s->kb, 0, LV_PART_ITEMS);
    lv_obj_set_style_bg_color(s->kb, COLOR_KB_SPEC, LV_PART_ITEMS | LV_STATE_PRESSED);
    lv_obj_set_style_bg_opa(s->kb, LV_OPA_COVER, LV_PART_ITEMS | LV_STATE_PRESSED);
    lv_obj_set_style_pad_all(s->kb, 2, LV_PART_MAIN);
    lv_obj_set_style_pad_gap(s->kb, 2, LV_PART_MAIN);

    s->kb_visible = false;

    ESP_LOGI(TAG, "Settings UI initialized (%dx%d)", (int)width, (int)height);
    return ESP_OK;
}

void settings_ui_load_config(settings_ui_t *s, const ln_config_t *cfg)
{
    if (!s || !cfg) return;

    if (cfg->wifi_ssid[0]) lv_textarea_set_text(s->ta_ssid, cfg->wifi_ssid);
    if (cfg->wifi_pass[0]) lv_textarea_set_text(s->ta_pass, cfg->wifi_pass);
    if (cfg->mqtt_broker[0]) lv_textarea_set_text(s->ta_broker, cfg->mqtt_broker);
    if (cfg->mqtt_client[0]) lv_textarea_set_text(s->ta_client, cfg->mqtt_client);

    if (s->slider_brightness) {
        int br = cfg->brightness > 0 ? cfg->brightness : 80;
        lv_slider_set_value(s->slider_brightness, br, LV_ANIM_OFF);
        char buf[16];
        snprintf(buf, sizeof(buf), "%d%%", br);
        lv_label_set_text(s->lbl_brightness_val, buf);
    }
    if (s->slider_volume) {
        int vol = cfg->volume > 0 ? cfg->volume : 50;
        lv_slider_set_value(s->slider_volume, vol, LV_ANIM_OFF);
        char buf[16];
        snprintf(buf, sizeof(buf), "%d%%", vol);
        lv_label_set_text(s->lbl_volume_val, buf);
    }
}

void settings_ui_hide_keyboard(settings_ui_t *s)
{
    if (!s || !s->kb_visible) return;

    lv_keyboard_set_textarea(s->kb, NULL);
    lv_obj_add_flag(s->kb_cont, LV_OBJ_FLAG_HIDDEN);
    lv_obj_set_height(s->kb_cont, 0);
    s->kb_visible = false;

    if (s->ta_ssid) lv_obj_remove_state(s->ta_ssid, LV_STATE_FOCUSED);
    if (s->ta_pass) lv_obj_remove_state(s->ta_pass, LV_STATE_FOCUSED);
    if (s->ta_broker) lv_obj_remove_state(s->ta_broker, LV_STATE_FOCUSED);
    if (s->ta_client) lv_obj_remove_state(s->ta_client, LV_STATE_FOCUSED);
}

void settings_ui_set_back_cb(settings_ui_t *s, settings_back_cb_t cb)
{
    if (s) s->back_cb = cb;
}
