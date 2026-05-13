#include <string.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_vfs_fat.h"
#include "driver/sdmmc_host.h"
#include "sdmmc_cmd.h"
#include "sd_pwr_ctrl_by_on_chip_ldo.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "nvs_flash.h"

#include "pin_config.h"
#include "mipi_lcd.h"
#include "wifi_mgr.h"
#include "eth_mgr.h"
#include "app_mqtt.h"
#include "avatar_engine.h"
#include "web_config.h"
#include "touch_driver.h"
#include "chat_ui.h"
#include "settings_ui.h"
#include "time_mgr.h"
#include "spi_frame_rx.h"
#include "lvgl.h"
#include "esp_lvgl_port.h"

static const char *TAG = "main";

#define DEFAULT_WIFI_SSID      CONFIG_LN_WIFI_SSID
#define DEFAULT_WIFI_PASS      CONFIG_LN_WIFI_PASSWORD
#define DEFAULT_MQTT_BROKER    CONFIG_LN_MQTT_BROKER
#define DEFAULT_MQTT_CLIENT_ID CONFIG_LN_MQTT_CLIENT_ID

#define TOPIC_CMD      "luominest/p4/cmd"
#define TOPIC_STATUS   "luominest/p4/status"
#define TOPIC_STREAM   "luominest/p4/stream"
#define TOPIC_CHAT     "luominest/p4/chat"

#define STATUS_INTERVAL_MS (CONFIG_LN_STATUS_INTERVAL_SEC * 1000)

#define SCREEN_W       1024
#define SCREEN_H       600
#define STATUS_BAR_H   24
#define CONTENT_H      (SCREEN_H - STATUS_BAR_H)
#define LEFT_PANEL_W   560
#define RIGHT_PANEL_W  (SCREEN_W - LEFT_PANEL_W)

static lv_display_t *s_disp = NULL;
static lv_indev_t *s_touch_indev = NULL;
static ln_config_t s_device_config = {0};
static lv_obj_t *s_status_label = NULL;
static lv_obj_t *s_net_label = NULL;
static lv_obj_t *s_speed_label = NULL;
static lv_obj_t *s_time_label = NULL;
static lv_obj_t *s_right_panel = NULL;
static chat_ui_t s_chat = {0};
static settings_ui_t s_settings = {0};
static lv_obj_t *s_swipe_cont = NULL;
static lv_obj_t *s_page_dots[2] = {NULL, NULL};

typedef struct {
    uint8_t *data;
    uint32_t len;
} frame_msg_t;

#define FRAME_QUEUE_LEN 2
static QueueHandle_t s_frame_queue = NULL;

static volatile uint32_t s_stream_bytes = 0;
static uint32_t s_last_stream_bytes = 0;
static float s_current_speed_kbps = 0;

#define COLOR_BG          lv_color_hex(0x0F0F1A)
#define COLOR_STATUS_BG   lv_color_hex(0x161628)
#define COLOR_STATUS_TEXT lv_color_hex(0x7878A0)
#define COLOR_ONLINE      lv_color_hex(0x4ECDC4)
#define COLOR_OFFLINE     lv_color_hex(0xFF6B6B)
#define COLOR_CONNECTING  lv_color_hex(0xFFD93D)

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

static void gear_click_cb(lv_event_t *e)
{
    if (!s_swipe_cont) return;
    lv_obj_scroll_to_x(s_swipe_cont, SCREEN_W, LV_ANIM_ON);
    update_page_dots(1);
}

static void settings_go_back(void)
{
    if (!s_swipe_cont) return;
    lv_obj_scroll_to_x(s_swipe_cont, 0, LV_ANIM_ON);
    update_page_dots(0);
}

static void create_ui(void)
{
    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, COLOR_BG, LV_PART_MAIN);
    lv_obj_set_scrollbar_mode(scr, LV_SCROLLBAR_MODE_OFF);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);

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

    lv_obj_t *spacer = lv_obj_create(status_bar);
    lv_obj_remove_style_all(spacer);
    lv_obj_set_flex_grow(spacer, 1);
    lv_obj_set_size(spacer, 0, 0);

    s_speed_label = lv_label_create(status_bar);
    lv_label_set_text(s_speed_label, "");
    lv_obj_set_style_text_color(s_speed_label, lv_color_hex(0x6688AA), 0);
    lv_obj_set_style_text_font(s_speed_label, &lv_font_montserrat_14, 0);

    lv_obj_t *sep3 = lv_label_create(status_bar);
    lv_label_set_text(sep3, "  ");
    lv_obj_set_style_text_font(sep3, &lv_font_montserrat_14, 0);

    s_time_label = lv_label_create(status_bar);
    lv_label_set_text(s_time_label, "--:--");
    lv_obj_set_style_text_color(s_time_label, lv_color_hex(0xA0A0D0), 0);
    lv_obj_set_style_text_font(s_time_label, &lv_font_montserrat_14, 0);

    lv_obj_t *sep4 = lv_label_create(status_bar);
    lv_label_set_text(sep4, " ");
    lv_obj_set_style_text_font(sep4, &lv_font_montserrat_14, 0);

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

    lv_obj_t *page0 = lv_obj_create(s_swipe_cont);
    lv_obj_remove_style_all(page0);
    lv_obj_set_size(page0, SCREEN_W, CONTENT_H);
    lv_obj_set_style_bg_opa(page0, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(page0, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_flex_flow(page0, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(page0, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_START);

    lv_obj_t *left_panel = lv_obj_create(page0);
    lv_obj_remove_style_all(left_panel);
    lv_obj_set_size(left_panel, LEFT_PANEL_W, CONTENT_H);
    lv_obj_set_style_bg_opa(left_panel, LV_OPA_TRANSP, 0);
    lv_obj_clear_flag(left_panel, LV_OBJ_FLAG_SCROLLABLE);

    chat_ui_init(&s_chat, left_panel, LEFT_PANEL_W, CONTENT_H);

    s_right_panel = lv_obj_create(page0);
    lv_obj_remove_style_all(s_right_panel);
    lv_obj_set_size(s_right_panel, RIGHT_PANEL_W, CONTENT_H);
    lv_obj_set_style_bg_color(s_right_panel, COLOR_BG, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(s_right_panel, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_clear_flag(s_right_panel, LV_OBJ_FLAG_SCROLLABLE);

    lv_obj_t *page1 = lv_obj_create(s_swipe_cont);
    lv_obj_remove_style_all(page1);
    lv_obj_set_size(page1, SCREEN_W, CONTENT_H);
    lv_obj_set_style_bg_color(page1, COLOR_BG, LV_PART_MAIN);
    lv_obj_set_style_bg_opa(page1, LV_OPA_COVER, LV_PART_MAIN);
    lv_obj_clear_flag(page1, LV_OBJ_FLAG_SCROLLABLE);

    settings_ui_init(&s_settings, page1, SCREEN_W, CONTENT_H);
    settings_ui_set_back_cb(&s_settings, settings_go_back);

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

    lv_obj_scroll_to_x(s_swipe_cont, 0, LV_ANIM_OFF);
}

static void touch_init_task(void *pvParameter)
{
    ESP_LOGI(TAG, "Touch init task started");
    esp_err_t ret = touch_driver_init(s_disp, &s_touch_indev);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "Touch driver initialized successfully");
    } else {
        ESP_LOGW(TAG, "Touch driver init failed (0x%x)", ret);
    }
    vTaskDelete(NULL);
}

static void update_net_info(void)
{
    if (!s_net_label) return;

    char buf[80] = {0};
    bool eth_up = eth_mgr_is_connected();
    bool wifi_up = wifi_mgr_is_connected();

    if (eth_up) {
        char ip[16] = {0};
        eth_mgr_get_ip_str(ip, sizeof(ip));
        snprintf(buf, sizeof(buf), LV_SYMBOL_DRIVE " ETH %s", ip);
    } else if (wifi_up) {
        char ip[16] = {0};
        wifi_mgr_get_ip_str(ip, sizeof(ip));
        int8_t rssi = wifi_mgr_get_rssi();
        snprintf(buf, sizeof(buf), LV_SYMBOL_WIFI " %s %ddBm", ip, rssi);
    } else {
        snprintf(buf, sizeof(buf), LV_SYMBOL_WARNING " No network");
    }

    lvgl_port_lock(5000);
    lv_label_set_text(s_net_label, buf);
    if (eth_up || wifi_up) {
        lv_obj_set_style_text_color(s_net_label, lv_color_hex(0x88CCAA), 0);
    } else {
        lv_obj_set_style_text_color(s_net_label, COLOR_OFFLINE, 0);
    }
    lvgl_port_unlock();
}

static void update_speed_display(void)
{
    if (!s_speed_label) return;

    uint32_t current = s_stream_bytes;
    uint32_t delta = current - s_last_stream_bytes;
    s_last_stream_bytes = current;
    s_current_speed_kbps = (float)(delta) / 1024.0f;

    char buf[32] = {0};
    if (s_current_speed_kbps > 1024.0f) {
        snprintf(buf, sizeof(buf), "%.1f MB/s", s_current_speed_kbps / 1024.0f);
    } else if (s_current_speed_kbps > 0.1f) {
        snprintf(buf, sizeof(buf), "%.0f KB/s", s_current_speed_kbps);
    } else {
        buf[0] = '\0';
    }

    lvgl_port_lock(5000);
    lv_label_set_text(s_speed_label, buf);
    lvgl_port_unlock();
}

static void update_ui_online(void)
{
    if (s_status_label) {
        lvgl_port_lock(5000);
        lv_label_set_text(s_status_label, LV_SYMBOL_WIFI " Online");
        lv_obj_set_style_text_color(s_status_label, COLOR_ONLINE, 0);
        lvgl_port_unlock();
    }
    update_net_info();
}

static void update_ui_offline(void)
{
    if (s_status_label) {
        lvgl_port_lock(5000);
        lv_label_set_text(s_status_label, LV_SYMBOL_WARNING " Offline");
        lv_obj_set_style_text_color(s_status_label, COLOR_OFFLINE, 0);
        lvgl_port_unlock();
    }
    update_net_info();
}

static void update_ui_ap_mode(void)
{
    if (s_status_label) {
        lvgl_port_lock(5000);
        lv_label_set_text(s_status_label, LV_SYMBOL_WIFI " AP Mode");
        lv_obj_set_style_text_color(s_status_label, COLOR_CONNECTING, 0);
        lvgl_port_unlock();
    }
    update_net_info();
}

static void on_mqtt_command(const char *topic, const char *data, int data_len)
{
    ESP_LOGI(TAG, "CMD [%s]: %.*s", topic, data_len, data);

    if (strcmp(topic, TOPIC_CMD) == 0) {
        if (strstr(data, "happy")) {
            avatar_engine_play_state(AVATAR_STATE_HAPPY);
        } else if (strstr(data, "sad")) {
            avatar_engine_play_state(AVATAR_STATE_SAD);
        } else if (strstr(data, "angry")) {
            avatar_engine_play_state(AVATAR_STATE_ANGRY);
        } else if (strstr(data, "surprised")) {
            avatar_engine_play_state(AVATAR_STATE_SURPRISED);
        } else if (strstr(data, "think")) {
            avatar_engine_play_state(AVATAR_STATE_THINK);
        } else if (strstr(data, "neutral")) {
            avatar_engine_play_state(AVATAR_STATE_NEUTRAL);
        } else if (strstr(data, "talk")) {
            avatar_engine_play_state(AVATAR_STATE_TALK);
        } else if (strstr(data, "idle")) {
            avatar_engine_play_state(AVATAR_STATE_IDLE);
        } else if (strstr(data, "stop")) {
            avatar_engine_stop();
        }
    } else if (strcmp(topic, TOPIC_CHAT) == 0) {
        if (!data || data_len <= 0) return;

        chat_msg_role_t role = CHAT_MSG_ASSISTANT;
        const char *text = data;
        int text_len = data_len;

        if (data_len > 2 && data[0] == 'U' && data[1] == ':') {
            role = CHAT_MSG_USER;
            text = data + 2;
            text_len = data_len - 2;
        } else if (data_len > 2 && data[0] == 'A' && data[1] == ':') {
            role = CHAT_MSG_ASSISTANT;
            text = data + 2;
            text_len = data_len - 2;
        }

        char buf[CHAT_MSG_MAX_LEN];
        int copy_len = text_len < (CHAT_MSG_MAX_LEN - 1) ? text_len : (CHAT_MSG_MAX_LEN - 1);
        memcpy(buf, text, copy_len);
        buf[copy_len] = '\0';

        lvgl_port_lock(5000);
        chat_ui_add_message(&s_chat, role, buf);
        lvgl_port_unlock();
    }
}

static void on_spi_frame(const uint8_t *data, uint32_t len)
{
    if (!s_frame_queue) return;

    s_stream_bytes += len;

    frame_msg_t msg = {0};
    msg.len = len;
    msg.data = heap_caps_malloc(len, MALLOC_CAP_SPIRAM);
    if (!msg.data) return;
    memcpy(msg.data, data, len);

    frame_msg_t discarded = {0};
    if (xQueueSend(s_frame_queue, &msg, 0) != pdTRUE) {
        if (xQueueReceive(s_frame_queue, &discarded, 0) == pdTRUE) {
            free(discarded.data);
        }
        xQueueSend(s_frame_queue, &msg, 0);
    }
}

static void on_mqtt_stream(const char *topic, const uint8_t *data, int data_len)
{
    if (strcmp(topic, TOPIC_STREAM) != 0) return;
    if (!s_frame_queue) return;

    s_stream_bytes += data_len;

    frame_msg_t msg = {0};
    msg.len = data_len;
    msg.data = heap_caps_malloc(data_len, MALLOC_CAP_SPIRAM);
    if (!msg.data) {
        ESP_LOGE(TAG, "No PSRAM for frame (%d bytes)", data_len);
        return;
    }
    memcpy(msg.data, data, data_len);

    frame_msg_t discarded = {0};
    if (xQueueSend(s_frame_queue, &msg, 0) != pdTRUE) {
        if (xQueueReceive(s_frame_queue, &discarded, 0) == pdTRUE) {
            free(discarded.data);
        }
        xQueueSend(s_frame_queue, &msg, 0);
    }
}

static void frame_decode_task(void *pvParameter)
{
    frame_msg_t msg = {0};
    while (1) {
        if (xQueueReceive(s_frame_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE) {
            avatar_engine_show_frame(msg.data, msg.len);
            free(msg.data);
            msg.data = NULL;
        } else {
            vTaskDelay(pdMS_TO_TICKS(1));
        }
    }
}

static void on_mqtt_connected(void)
{
    ESP_LOGI(TAG, "MQTT connected, subscribing...");
    app_mqtt_subscribe(TOPIC_CMD, 1);
    app_mqtt_subscribe(TOPIC_STREAM, 0);
    app_mqtt_subscribe(TOPIC_CHAT, 1);
    update_ui_online();
}

static void on_mqtt_disconnected(void)
{
    ESP_LOGW(TAG, "MQTT disconnected, will auto-reconnect");
    update_ui_offline();
}

static bool s_mqtt_started = false;
static bool s_sntp_started = false;

static void start_sntp(void)
{
    if (s_sntp_started) return;
    s_sntp_started = true;
    time_mgr_init();
}

static void start_mqtt(void)
{
    if (s_mqtt_started) return;
    s_mqtt_started = true;

    const char *broker = s_device_config.mqtt_broker[0] ? s_device_config.mqtt_broker : DEFAULT_MQTT_BROKER;
    const char *client = s_device_config.mqtt_client[0] ? s_device_config.mqtt_client : DEFAULT_MQTT_CLIENT_ID;
    app_mqtt_init(broker, client);
    app_mqtt_register_message_cb(on_mqtt_command);
    app_mqtt_register_stream_cb(on_mqtt_stream);
    app_mqtt_register_connected_cb(on_mqtt_connected);
    app_mqtt_register_disconnected_cb(on_mqtt_disconnected);
}

static void on_eth_connected(void)
{
    ESP_LOGI(TAG, "Ethernet connected, starting MQTT...");
    if (wifi_mgr_is_connected()) {
        ESP_LOGI(TAG, "WiFi also online, preferring ETH - stopping WiFi");
        wifi_mgr_disconnect();
    }
    start_sntp();
    start_mqtt();
}

static void on_eth_disconnected(void)
{
    ESP_LOGW(TAG, "Ethernet disconnected, falling back to WiFi...");
    if (!wifi_mgr_is_connected()) {
        if (s_device_config.wifi_ssid[0]) {
            wifi_mgr_connect_async(s_device_config.wifi_ssid, s_device_config.wifi_pass);
        } else {
            update_ui_offline();
        }
    }
}

static void on_wifi_connected(void)
{
    ESP_LOGI(TAG, "WiFi connected, starting MQTT...");
    start_sntp();
    start_mqtt();
}

static void on_wifi_disconnected(void)
{
    ESP_LOGW(TAG, "WiFi disconnected");
    if (eth_mgr_is_connected()) {
        ESP_LOGI(TAG, "ETH still online, ignoring WiFi disconnect");
    } else {
        update_ui_offline();
    }
}

static void update_time_display(void)
{
    if (!s_time_label) return;

    char buf[16];
    time_mgr_get_local_time_str(buf, sizeof(buf));

    lvgl_port_lock(5000);
    lv_label_set_text(s_time_label, buf);
    lvgl_port_unlock();
}

static void status_task(void *pvParameter)
{
    char status_buf[256];
    int tick = 0;
    int speed_tick = 0;
    int status_interval_ticks = STATUS_INTERVAL_MS / 1000;
    if (status_interval_ticks < 1) status_interval_ticks = 1;
    int speed_interval_ticks = 3;

    while (1) {
        update_time_display();

        tick++;
        speed_tick++;

        if (speed_tick >= speed_interval_ticks) {
            speed_tick = 0;
            update_net_info();
            update_speed_display();
        }

        if (tick >= status_interval_ticks) {
            tick = 0;

            if (app_mqtt_is_connected()) {
                const avatar_stats_t *stats = avatar_engine_get_stats();
                int8_t rssi = wifi_mgr_get_rssi();
                bool eth_up = eth_mgr_is_connected();
                uint32_t free_heap = esp_get_free_heap_size();
                uint32_t free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);

                snprintf(status_buf, sizeof(status_buf),
                         "{\"state\":\"online\",\"eth\":%s,\"rssi\":%d,\"heap\":%u,\"psram\":%u,"
                         "\"frames\":{\"rx\":%u,\"show\":%u,\"dedup\":%u,\"err\":%u},"
                         "\"decode_ms\":%u}",
                         eth_up ? "true" : "false", rssi, (unsigned)free_heap, (unsigned)free_psram,
                         (unsigned)stats->frames_received,
                         (unsigned)stats->frames_displayed,
                         (unsigned)stats->frames_skipped_dedup,
                         (unsigned)stats->frames_skipped_error,
                         (unsigned)stats->last_decode_ms);

                app_mqtt_publish(TOPIC_STATUS, status_buf, strlen(status_buf), 1);
            }
        }

        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

static esp_err_t init_sdcard(void)
{
    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    host.slot = SDMMC_HOST_SLOT_0;
    host.max_freq_khz = SDMMC_FREQ_HIGHSPEED;

    sd_pwr_ctrl_ldo_config_t ldo_config = {
        .ldo_chan_id = SD_LDO_CHAN,
    };
    sd_pwr_ctrl_handle_t pwr_ctrl_handle = NULL;
    esp_err_t ret = sd_pwr_ctrl_new_on_chip_ldo(&ldo_config, &pwr_ctrl_handle);
    if (ret == ESP_OK) {
        host.pwr_ctrl_handle = pwr_ctrl_handle;
        vTaskDelay(pdMS_TO_TICKS(200));
    } else {
        ESP_LOGW(TAG, "SD LDO power control init failed (0x%x), continuing without", ret);
    }

    sdmmc_slot_config_t slot_config = {
        .clk = SDMMC_CLK_PIN,
        .cmd = SDMMC_CMD_PIN,
        .d0 = SDMMC_D0_PIN,
        .d1 = SDMMC_D1_PIN,
        .d2 = SDMMC_D2_PIN,
        .d3 = SDMMC_D3_PIN,
        .d4 = GPIO_NUM_NC,
        .d5 = GPIO_NUM_NC,
        .d6 = GPIO_NUM_NC,
        .d7 = GPIO_NUM_NC,
        .cd = SDMMC_SLOT_NO_CD,
        .wp = SDMMC_SLOT_NO_WP,
        .width = 4,
        .flags = 0,
    };

    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 10,
        .allocation_unit_size = 16 * 1024,
    };

    sdmmc_card_t *card = NULL;
    ret = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot_config,
                                           &mount_config, &card);
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "SD card mount failed (0x%x), continuing without SD", ret);
        ESP_LOGW(TAG, "Hint: ensure SD card is FAT32 formatted and properly inserted");
        return ret;
    }

    ESP_LOGI(TAG, "SD card mounted successfully");
    sdmmc_card_print_info(stdout, card);
    return ESP_OK;
}

static void load_device_config(void)
{
    if (web_config_load(&s_device_config) == ESP_OK && web_config_has_saved()) {
        ESP_LOGI(TAG, "Loaded config from NVS: SSID=%s, Broker=%s, Brightness=%d, Volume=%d",
                 s_device_config.wifi_ssid, s_device_config.mqtt_broker,
                 s_device_config.brightness, s_device_config.volume);
    } else {
        ESP_LOGI(TAG, "No saved config, using defaults from menuconfig");
        strncpy(s_device_config.wifi_ssid, DEFAULT_WIFI_SSID, sizeof(s_device_config.wifi_ssid) - 1);
        strncpy(s_device_config.wifi_pass, DEFAULT_WIFI_PASS, sizeof(s_device_config.wifi_pass) - 1);
        strncpy(s_device_config.mqtt_broker, DEFAULT_MQTT_BROKER, sizeof(s_device_config.mqtt_broker) - 1);
        strncpy(s_device_config.mqtt_client, DEFAULT_MQTT_CLIENT_ID, sizeof(s_device_config.mqtt_client) - 1);
        s_device_config.brightness = 100;
        s_device_config.volume = 50;
    }
}

void app_main(void)
{
    esp_log_level_set("H_API", ESP_LOG_WARN);
    esp_log_level_set("H_SDIO_DRV", ESP_LOG_WARN);
    esp_log_level_set("lcd_panel", ESP_LOG_WARN);

    ESP_LOGI(TAG, "=== LuomiNest P4 Firmware ===");
    ESP_LOGI(TAG, "Free heap: %u, Free PSRAM: %u",
             (unsigned)esp_get_free_heap_size(),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

    mipi_lcd_handle_t lcd = {
        .rst_pin = LCD_RST_PIN,
        .bl_pin = LCD_BL_PIN,
        .width = MIPI_LCD_WIDTH,
        .height = MIPI_LCD_HEIGHT,
    };

    ESP_LOGI(TAG, "Initializing MIPI DSI LCD...");
    ESP_ERROR_CHECK(mipi_lcd_init(&lcd));

    ESP_LOGI(TAG, "Initializing LVGL port...");
    const lvgl_port_cfg_t lvgl_cfg = ESP_LVGL_PORT_INIT_CONFIG();
    ESP_ERROR_CHECK(lvgl_port_init(&lvgl_cfg));

    const lvgl_port_display_cfg_t disp_cfg = {
        .io_handle = lcd.io,
        .panel_handle = lcd.dpi_panel,
        .control_handle = lcd.control,
        .buffer_size = MIPI_LCD_WIDTH * MIPI_LCD_HEIGHT,
        .double_buffer = 1,
        .hres = MIPI_LCD_WIDTH,
        .vres = MIPI_LCD_HEIGHT,
        .monochrome = false,
        .rotation = {
            .swap_xy = false,
            .mirror_x = false,
            .mirror_y = false,
        },
        .color_format = LV_COLOR_FORMAT_RGB565,
        .flags = {
            .buff_dma = false,
            .buff_spiram = true,
            .sw_rotate = false,
            .full_refresh = true,
        },
    };
    const lvgl_port_display_dsi_cfg_t dpi_cfg = {
        .flags = {
            .avoid_tearing = true,
        },
    };
    s_disp = lvgl_port_add_disp_dsi(&disp_cfg, &dpi_cfg);
    if (!s_disp) {
        ESP_LOGE(TAG, "Failed to add DSI display to LVGL");
        return;
    }

    lvgl_port_lock(5000);
    create_ui();
    lvgl_port_unlock();

    lvgl_port_lock(5000);
    ESP_ERROR_CHECK(avatar_engine_init(s_right_panel));
    lvgl_port_unlock();

    lvgl_port_lock(5000);
    chat_ui_add_demo_messages(&s_chat);
    lvgl_port_unlock();

    load_device_config();

    vTaskDelay(pdMS_TO_TICKS(100));
    int init_brightness = s_device_config.brightness > 0 ? s_device_config.brightness : 100;
    mipi_lcd_brightness_set(init_brightness);
    ESP_LOGI(TAG, "Backlight on (brightness %d%%), UI visible", init_brightness);

    xTaskCreatePinnedToCore(touch_init_task, "touch_init", 8192, NULL, 5, NULL, 0);

    init_sdcard();

    s_frame_queue = xQueueCreate(FRAME_QUEUE_LEN, sizeof(frame_msg_t));
    xTaskCreatePinnedToCore(frame_decode_task, "frame_dec", 8192, NULL, 4, NULL, 1);

    wifi_mgr_register_connected_cb(on_wifi_connected);
    wifi_mgr_register_disconnected_cb(on_wifi_disconnected);

    eth_mgr_register_connected_cb(on_eth_connected);
    eth_mgr_register_disconnected_cb(on_eth_disconnected);

    lvgl_port_lock(5000);
    settings_ui_load_config(&s_settings, &s_device_config);
    lvgl_port_unlock();

    ESP_LOGI(TAG, "Initializing Ethernet (EMAC + RMII)...");
    esp_err_t eth_init_ret = eth_mgr_init();
    bool eth_connected = false;

    if (eth_init_ret == ESP_OK) {
        eth_mgr_start();
        ESP_LOGI(TAG, "Waiting for Ethernet connection (%dms)...", CONFIG_LN_ETH_CONNECT_TIMEOUT_MS);
        int waited = 0;
        while (waited < CONFIG_LN_ETH_CONNECT_TIMEOUT_MS) {
            vTaskDelay(pdMS_TO_TICKS(500));
            waited += 500;
            if (eth_mgr_is_connected()) {
                eth_connected = true;
                break;
            }
        }
        if (eth_connected) {
            ESP_LOGI(TAG, "Ethernet connected! (waited %dms)", waited);
        } else {
            ESP_LOGW(TAG, "Ethernet not connected after %dms, trying WiFi...", waited);
        }
    } else {
        ESP_LOGW(TAG, "Ethernet init failed (0x%x), trying WiFi...", eth_init_ret);
    }

    if (!eth_connected) {
        wifi_mgr_init();
        ESP_LOGI(TAG, "WiFi SSID: %s", s_device_config.wifi_ssid);
        esp_err_t wifi_result = wifi_mgr_connect(s_device_config.wifi_ssid, s_device_config.wifi_pass);

        if (wifi_result == ESP_OK) {
            ESP_LOGI(TAG, "WiFi connected");
        } else {
            ESP_LOGW(TAG, "WiFi connection failed, starting AP config portal...");
            esp_err_t ap_result = web_config_start_ap();
            if (ap_result == ESP_OK) {
                update_ui_ap_mode();
            } else {
                update_ui_offline();
            }
        }
    } else {
        wifi_mgr_init();
        ESP_LOGI(TAG, "WiFi manager pre-initialized for fallback (ETH is primary)");
    }

    if (s_mqtt_started || eth_connected || wifi_mgr_is_connected()) {
        xTaskCreatePinnedToCore(status_task, "status", 4096, NULL, 2, NULL, 1);
    }

    esp_err_t spi_ret = spi_frame_rx_init();
    if (spi_ret == ESP_OK) {
        spi_frame_rx_register_cb(on_spi_frame);
        spi_frame_rx_start();
        ESP_LOGI(TAG, "SPI frame receiver (C6 coordinator) initialized");
    } else {
        ESP_LOGW(TAG, "SPI frame receiver not available (0x%x), using MQTT only", spi_ret);
    }

    ESP_LOGI(TAG, "LuomiNest P4 ready! Free heap: %u, Free PSRAM: %u",
             (unsigned)esp_get_free_heap_size(),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}
