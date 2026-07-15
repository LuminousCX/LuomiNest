/**
 * LuomiNest P4 - APP UI 全屏布局管理
 * 从旧 esp32-p4/main/main.c create_ui() 移植, 适配新分层架构:
 *   - 状态栏 (24px): "LuomiNest" + 连接状态 + 网络 + 时间 + 设置齿轮
 *   - 水平滑动容器: Page 0 (左 chat 560px + 右 avatar 464px) / Page 1 (设置全屏)
 *   - 底部页码指示器 (2 dots)
 *   - 滑动切换 + 齿轮按钮跳转 + 设置页返回
 */

#include "app_ui.h"
#include "app_chat.h"
#include "app_avatar.h"
#include "app_status.h"
#include "settings_ui.h"
#include "web_config.h"

#include "esp_log.h"
#include "esp_check.h"
#include "esp_timer.h"

#include "esp_lvgl_port.h"
#include "lvgl.h"
/* PPA draw unit init 入口不在 lvgl.h 公开路径, 需单独 include (lvgl 组件 src/ 在 INCLUDE_DIRS) */
#include "draw/espressif/ppa/lv_draw_ppa.h"

#include <string.h>

static const char *TAG = "app_ui";

/* === 手势配置 === */
#define DOUBLE_CLICK_MS  300

/* === 布局常量 (与旧工程一致) === */
#define SCREEN_W       1024
#define SCREEN_H       600
#define STATUS_BAR_H   24
#define CONTENT_H      (SCREEN_H - STATUS_BAR_H)
#define LEFT_PANEL_W   560
#define RIGHT_PANEL_W  (SCREEN_W - LEFT_PANEL_W)

/* === 颜色 (旧工程暗色主题) === */
#define COLOR_BG          lv_color_hex(0x0F0F1A)
#define COLOR_STATUS_BG   lv_color_hex(0x161628)
#define COLOR_STATUS_TEXT lv_color_hex(0x7878A0)
#define COLOR_ONLINE      lv_color_hex(0x4ECDC4)
#define COLOR_CONNECTING  lv_color_hex(0xFFD93D)

/* === 静态 widget 指针 === */
static lv_obj_t      *s_status_label = NULL;
static lv_obj_t      *s_net_label    = NULL;
static lv_obj_t      *s_time_label   = NULL;
static lv_obj_t      *s_swipe_cont   = NULL;
static lv_obj_t      *s_page_dots[2] = {NULL, NULL};
static lv_obj_t      *s_right_panel  = NULL;
static settings_ui_t  s_settings     = {0};

/* === 页码指示器更新 === */
static void update_page_dots(int page)
{
    for (int i = 0; i < 2; i++) {
        if (!s_page_dots[i]) continue;
        lv_obj_set_style_bg_color(s_page_dots[i],
            i == page ? COLOR_ONLINE : lv_color_hex(0x3A3A5C), 0);
        lv_obj_set_style_bg_opa(s_page_dots[i],
            i == page ? LV_OPA_COVER : LV_OPA_50, 0);
    }
}

/* === 滑动回调: 更新页码 + 离开设置页时收键盘 === */
static void swipe_scroll_cb(lv_event_t *e)
{
    lv_obj_t *cont = lv_event_get_target(e);
    lv_coord_t scroll_x = lv_obj_get_scroll_x(cont);
    int page = (scroll_x + SCREEN_W / 2) / SCREEN_W;
    if (page < 0) page = 0;
    if (page > 1) page = 1;
    update_page_dots(page);

    if (page != 0 && s_settings.kb_visible) {
        settings_ui_hide_keyboard(&s_settings);
    }
}

/* === 齿轮按钮: 跳到设置页 === */
static void gear_click_cb(lv_event_t *e)
{
    (void)e;
    if (!s_swipe_cont) return;
    lv_obj_scroll_to_x(s_swipe_cont, SCREEN_W, LV_ANIM_ON);
    update_page_dots(1);
}

/* === 设置页返回: 跳回主页 === */
static void settings_go_back(void)
{
    if (!s_swipe_cont) return;
    lv_obj_scroll_to_x(s_swipe_cont, 0, LV_ANIM_ON);
    update_page_dots(0);
}

/* === 手势回调 (LVGL indev 事件) === */
static int64_t s_last_click_us = 0;

static void screen_click_cb(lv_event_t *e)
{
    (void)e;
    int64_t now = esp_timer_get_time();

    /* 双击检测: 300ms 内两次点击 */
    if (s_last_click_us != 0 && (now - s_last_click_us) < (int64_t)DOUBLE_CLICK_MS * 1000) {
        s_last_click_us = 0;
        app_status_set_state(APP_STATE_CHAT);
        ESP_LOGI(TAG, "double click: state -> CHAT");
        return;
    }
    s_last_click_us = now;

    /* 单击: 推 chat 气泡 */
    esp_err_t cr = app_chat_push_message(CHAT_ROLE_USER, "Tap");
    if (cr != ESP_OK) {
        ESP_LOGW(TAG, "click chat push failed: %s", esp_err_to_name(cr));
    }
}

static void screen_long_press_cb(lv_event_t *e)
{
    (void)e;
    app_state_t cur  = app_status_get_state();
    app_state_t next = (app_state_t)(((int)cur + 1) % 5);
    app_status_set_state(next);
    ESP_LOGI(TAG, "long press: state %d -> %d", (int)cur, (int)next);
}

/* === 公共 API === */

void app_ui_set_status(const char *text, lv_color_t color)
{
    if (!s_status_label) return;
    if (lvgl_port_lock(100)) {
        lv_label_set_text(s_status_label, text);
        lv_obj_set_style_text_color(s_status_label, color, 0);
        lvgl_port_unlock();
    }
}

void app_ui_set_net_info(const char *text)
{
    if (!s_net_label) return;
    if (lvgl_port_lock(100)) {
        lv_label_set_text(s_net_label, text);
        lvgl_port_unlock();
    }
}

void app_ui_set_time(const char *text)
{
    if (!s_time_label) return;
    if (lvgl_port_lock(100)) {
        lv_label_set_text(s_time_label, text);
        lvgl_port_unlock();
    }
}

esp_err_t app_ui_init(void)
{
    if (!lvgl_port_lock(5000)) {
        ESP_LOGE(TAG, "lvgl_port_lock failed");
        return ESP_ERR_INVALID_STATE;
    }

    /* 启用 P4 PPA 硬件加速 draw unit */
    lv_draw_ppa_init();

    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, COLOR_BG, LV_PART_MAIN);
    lv_obj_set_scrollbar_mode(scr, LV_SCROLLBAR_MODE_OFF);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

    /* ── 状态栏 (24px) ── */
    lv_obj_t *status_bar = lv_obj_create(scr);
    lv_obj_remove_style_all(status_bar);
    lv_obj_set_size(status_bar, SCREEN_W, STATUS_BAR_H);
    lv_obj_set_pos(status_bar, 0, 0);
    lv_obj_set_style_bg_color(status_bar, COLOR_STATUS_BG, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(status_bar, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_set_style_pad_left(status_bar, 12, 0);
    lv_obj_set_style_pad_right(status_bar, 12, 0);
    lv_obj_set_flex_flow(status_bar, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(status_bar, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_clear_flag(status_bar, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *title = lv_label_create(status_bar);
    lv_label_set_text(title, "LuomiNest");
    lv_obj_set_style_text_color(title, lv_color_hex(0xA0A0D0), 0);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_14, 0);

    lv_obj_t *sep1 = lv_label_create(status_bar);
    lv_label_set_text(sep1, "  ");
    lv_obj_set_style_text_font(sep1, &lv_font_montserrat_14, 0);

    s_status_label = lv_label_create(status_bar);
    lv_label_set_text(s_status_label, LV_SYMBOL_WARNING " Connecting");
    lv_obj_set_style_text_color(s_status_label, COLOR_CONNECTING, 0);
    lv_obj_set_style_text_font(s_status_label, &lv_font_montserrat_14, 0);

    lv_obj_t *sep2 = lv_label_create(status_bar);
    lv_label_set_text(sep2, "  ");
    lv_obj_set_style_text_font(sep2, &lv_font_montserrat_14, 0);

    s_net_label = lv_label_create(status_bar);
    lv_label_set_text(s_net_label, "");
    lv_obj_set_style_text_color(s_net_label, COLOR_STATUS_TEXT, 0);
    lv_obj_set_style_text_font(s_net_label, &lv_font_montserrat_14, 0);

    /* spacer: 把时间+齿轮推到右边 */
    lv_obj_t *spacer = lv_obj_create(status_bar);
    lv_obj_remove_style_all(spacer);
    lv_obj_set_flex_grow(spacer, 1);
    lv_obj_set_size(spacer, 0, 0);

    s_time_label = lv_label_create(status_bar);
    lv_label_set_text(s_time_label, "--:--");
    lv_obj_set_style_text_color(s_time_label, lv_color_hex(0xA0A0D0), 0);
    lv_obj_set_style_text_font(s_time_label, &lv_font_montserrat_14, 0);

    lv_obj_t *sep4 = lv_label_create(status_bar);
    lv_label_set_text(sep4, " ");
    lv_obj_set_style_text_font(sep4, &lv_font_montserrat_14, 0);

    /* 齿轮按钮 → 设置页 */
    lv_obj_t *gear_btn = lv_btn_create(status_bar);
    lv_obj_set_size(gear_btn, 20, 20);
    lv_obj_set_style_bg_opa(gear_btn, LV_OPA_TRANSP, 0);
    lv_obj_set_style_border_width(gear_btn, 0, 0);
    lv_obj_set_style_shadow_width(gear_btn, 0, 0);
    lv_obj_set_style_pad_all(gear_btn, 0, 0);
    lv_obj_add_event_cb(gear_btn, gear_click_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *gear_lbl = lv_label_create(gear_btn);
    lv_label_set_text(gear_lbl, LV_SYMBOL_SETTINGS);
    lv_obj_set_style_text_color(gear_lbl, COLOR_STATUS_TEXT, 0);
    lv_obj_set_style_text_font(gear_lbl, &lv_font_montserrat_14, 0);
    lv_obj_center(gear_lbl);

    /* ── 水平滑动容器 ── */
    s_swipe_cont = lv_obj_create(scr);
    lv_obj_remove_style_all(s_swipe_cont);
    lv_obj_set_size(s_swipe_cont, SCREEN_W, CONTENT_H);
    lv_obj_set_pos(s_swipe_cont, 0, STATUS_BAR_H);
    lv_obj_set_flex_flow(s_swipe_cont, LV_FLEX_FLOW_ROW);
    lv_obj_set_scroll_snap_x(s_swipe_cont, LV_SCROLL_SNAP_CENTER);
    lv_obj_set_scroll_dir(s_swipe_cont, LV_DIR_HOR);
    lv_obj_set_scrollbar_mode(s_swipe_cont, LV_SCROLLBAR_MODE_OFF);
    lv_obj_set_style_bg_opa(s_swipe_cont, LV_OPA_TRANSP, 0);
    lv_obj_set_style_pad_all(s_swipe_cont, 0, 0);
    lv_obj_set_style_pad_gap(s_swipe_cont, 0, 0);
    lv_obj_add_event_cb(s_swipe_cont, swipe_scroll_cb, LV_EVENT_SCROLL, NULL);
    lv_obj_add_event_cb(s_swipe_cont, screen_click_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(s_swipe_cont, screen_long_press_cb, LV_EVENT_LONG_PRESSED, NULL);

    /* ── Page 0: 主页 (左 chat + 右 avatar) ── */
    lv_obj_t *page0 = lv_obj_create(s_swipe_cont);
    lv_obj_remove_style_all(page0);
    lv_obj_set_size(page0, SCREEN_W, CONTENT_H);
    lv_obj_set_style_bg_opa(page0, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(page0, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(page0, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(page0, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);

    /* chat panel (左侧 560px) */
    lv_obj_t *left_panel = lv_obj_create(page0);
    lv_obj_remove_style_all(left_panel);
    lv_obj_set_size(left_panel, LEFT_PANEL_W, CONTENT_H);
    lv_obj_set_style_bg_opa(left_panel, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(left_panel, LV_OBJ_FLAG_SCROLLABLE);

    /* avatar panel (右侧 464px) */
    lv_obj_t *right_panel = lv_obj_create(page0);
    lv_obj_remove_style_all(right_panel);
    lv_obj_set_size(right_panel, RIGHT_PANEL_W, CONTENT_H);
    lv_obj_set_style_bg_color(right_panel, COLOR_BG, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(right_panel, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_clear_flag(right_panel, LV_OBJ_FLAG_SCROLLABLE);
    s_right_panel = right_panel;

    /* ── Page 1: 设置页 ── */
    lv_obj_t *page1 = lv_obj_create(s_swipe_cont);
    lv_obj_remove_style_all(page1);
    lv_obj_set_size(page1, SCREEN_W, CONTENT_H);
    lv_obj_set_style_bg_color(page1, COLOR_BG, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(page1, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_clear_flag(page1, LV_OBJ_FLAG_SCROLLABLE);

    /* ── 底部页码指示器 (2 dots) ── */
    lv_obj_t *dots_cont = lv_obj_create(scr);
    lv_obj_remove_style_all(dots_cont);
    lv_obj_set_size(dots_cont, 40, 8);
    lv_obj_align(dots_cont, LV_ALIGN_BOTTOM_MID, 0, -4);
    lv_obj_set_flex_flow(dots_cont, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(dots_cont, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
    lv_obj_set_style_pad_column(dots_cont, 6, 0);
    lv_obj_clear_flag(dots_cont, LV_OBJ_FLAG_SCROLLABLE);

    for (int i = 0; i < 2; i++) {
        s_page_dots[i] = lv_obj_create(dots_cont);
        lv_obj_remove_style_all(s_page_dots[i]);
        lv_obj_set_size(s_page_dots[i], i == 0 ? 16 : 6, 6);
        lv_obj_set_style_bg_color(s_page_dots[i], i == 0 ? COLOR_ONLINE : lv_color_hex(0x3A3A5C), 0);
        lv_obj_set_style_bg_opa(s_page_dots[i], i == 0 ? LV_OPA_COVER : LV_OPA_50, 0);
        lv_obj_set_style_radius(s_page_dots[i], 3, 0);
    }

    lvgl_port_unlock();

    /* ── 初始化子模块 ── */
    ESP_ERROR_CHECK(app_chat_init(left_panel));
    /* avatar 在 deferred_init_task 里初始化, 避免 PSRAM 分配阻塞主线程 */

    /* 设置页 */
    if (lvgl_port_lock(5000)) {
        settings_ui_init(&s_settings, page1, SCREEN_W, CONTENT_H);
        settings_ui_set_back_cb(&s_settings, settings_go_back);

        /* 加载 NVS 配置到设置页 */
        ln_config_t cfg = {0};
        web_config_load(&cfg);
        settings_ui_load_config(&s_settings, &cfg);

        lvgl_port_unlock();
    }

    ESP_LOGI(TAG, "UI ready: status bar + swipe (chat %dpx + avatar %dpx + settings page) + dots",
             LEFT_PANEL_W, RIGHT_PANEL_W);
    return ESP_OK;
}

lv_obj_t *app_ui_get_right_panel(void)
{
    return s_right_panel;
}
