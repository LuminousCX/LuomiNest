#include <string.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_task_wdt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include "pin_config.h"
#include "st7735s.h"
#include "lvgl_port.h"
#include "wifi_mgr.h"
#include "app_mqtt.h"
#include "avatar_engine.h"
#include "web_config.h"
#include "lvgl.h"

static const char *TAG = "main";

#define DEFAULT_WIFI_SSID      CONFIG_LN_WIFI_SSID
#define DEFAULT_WIFI_PASS      CONFIG_LN_WIFI_PASSWORD
#define DEFAULT_MQTT_BROKER    CONFIG_LN_MQTT_BROKER
#define DEFAULT_MQTT_CLIENT_ID CONFIG_LN_MQTT_CLIENT_ID

#define TOPIC_CMD      "luominest/s3/cmd"
#define TOPIC_STATUS   "luominest/s3/status"
#define TOPIC_STREAM   "luominest/s3/stream"

#define FRAME_QUEUE_LEN CONFIG_LN_FRAME_QUEUE_SIZE
#define STATUS_INTERVAL_MS (CONFIG_LN_STATUS_INTERVAL_SEC * 1000)

static st7735s_handle_t s_lcd = {0};
static lvgl_port_t s_lvgl_port = {0};
static ln_config_t s_device_config = {0};

typedef struct {
    uint8_t *data;
    uint32_t len;
} frame_msg_t;

static QueueHandle_t s_frame_queue = NULL;

static void on_mqtt_command(const char *topic, const char *data, int data_len)
{
    ESP_LOGI(TAG, "MQTT [%s]: %.*s", topic, data_len, data);

    if (strcmp(topic, TOPIC_CMD) == 0) {
        if (strstr(data, "happy")) {
            avatar_engine_play_state(AVATAR_STATE_HAPPY);
        } else if (strstr(data, "sad")) {
            avatar_engine_play_state(AVATAR_STATE_SAD);
        } else if (strstr(data, "angry")) {
            avatar_engine_play_state(AVATAR_STATE_ANGRY);
        } else if (strstr(data, "surprised")) {
            avatar_engine_play_state(AVATAR_STATE_SURPRISED);
        } else if (strstr(data, "wave")) {
            avatar_engine_play_state(AVATAR_STATE_WAVE);
        } else if (strstr(data, "nod")) {
            avatar_engine_play_state(AVATAR_STATE_NOD);
        } else if (strstr(data, "think")) {
            avatar_engine_play_state(AVATAR_STATE_THINK);
        } else if (strstr(data, "sleep")) {
            avatar_engine_play_state(AVATAR_STATE_SLEEP);
        } else if (strstr(data, "talk")) {
            avatar_engine_play_state(AVATAR_STATE_TALK);
        } else if (strstr(data, "idle")) {
            avatar_engine_play_state(AVATAR_STATE_IDLE);
        } else if (strstr(data, "stop")) {
            avatar_engine_stop();
        }
    }
}

static void on_mqtt_stream(const char *topic, const uint8_t *data, int data_len)
{
    if (strcmp(topic, TOPIC_STREAM) != 0) return;
    if (!s_frame_queue) return;

    frame_msg_t msg = {0};
    msg.len = data_len;
    msg.data = heap_caps_malloc(data_len, MALLOC_CAP_SPIRAM);
    if (!msg.data) {
        ESP_LOGD(TAG, "No PSRAM for frame copy (%d bytes)", data_len);
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
#if CONFIG_LN_ENABLE_WATCHDOG
    esp_task_wdt_add(NULL);
#endif
    while (1) {
#if CONFIG_LN_ENABLE_WATCHDOG
        esp_task_wdt_reset();
#endif
        if (xQueueReceive(s_frame_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE) {
            avatar_engine_show_frame(msg.data, msg.len);
            free(msg.data);
            msg.data = NULL;
        }
    }
}

static void on_mqtt_connected(void)
{
    ESP_LOGI(TAG, "MQTT connected, subscribing...");
    app_mqtt_subscribe(TOPIC_CMD, 1);
    app_mqtt_subscribe(TOPIC_STREAM, 0);
}

static void on_mqtt_disconnected(void)
{
    ESP_LOGW(TAG, "MQTT disconnected, will auto-reconnect");
}

static void on_wifi_connected(void)
{
    ESP_LOGI(TAG, "WiFi connected, starting MQTT...");
    const char *broker = s_device_config.mqtt_broker[0] ? s_device_config.mqtt_broker : DEFAULT_MQTT_BROKER;
    const char *client = s_device_config.mqtt_client[0] ? s_device_config.mqtt_client : DEFAULT_MQTT_CLIENT_ID;
    app_mqtt_init(broker, client);
    app_mqtt_register_message_cb(on_mqtt_command);
    app_mqtt_register_stream_cb(on_mqtt_stream);
    app_mqtt_register_connected_cb(on_mqtt_connected);
    app_mqtt_register_disconnected_cb(on_mqtt_disconnected);
}

static void on_wifi_disconnected(void)
{
    ESP_LOGW(TAG, "WiFi disconnected, MQTT paused until reconnected");
}

static void lvgl_task(void *pvParameter)
{
#if CONFIG_LN_ENABLE_WATCHDOG
    esp_task_wdt_add(NULL);
#endif
    while (1) {
#if CONFIG_LN_ENABLE_WATCHDOG
        esp_task_wdt_reset();
#endif
        lvgl_port_lock();
        lv_timer_handler();
        lvgl_port_unlock();
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

static void status_task(void *pvParameter)
{
    char status_buf[256];
    while (1) {
        if (app_mqtt_is_connected()) {
            const avatar_stats_t *stats = avatar_engine_get_stats();
            int8_t rssi = wifi_mgr_get_rssi();
            uint32_t free_heap = esp_get_free_heap_size();
            uint32_t free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);

            snprintf(status_buf, sizeof(status_buf),
                     "{\"state\":\"online\",\"rssi\":%d,\"heap\":%u,\"psram\":%u,"
                     "\"frames\":{\"rx\":%u,\"show\":%u,\"dedup\":%u,\"err\":%u},"
                     "\"decode_ms\":%u}",
                     rssi, (unsigned)free_heap, (unsigned)free_psram,
                     (unsigned)stats->frames_received,
                     (unsigned)stats->frames_displayed,
                     (unsigned)stats->frames_skipped_dedup,
                     (unsigned)stats->frames_skipped_error,
                     (unsigned)stats->last_decode_ms);

            app_mqtt_publish(TOPIC_STATUS, status_buf, strlen(status_buf), 1);
        }
        vTaskDelay(pdMS_TO_TICKS(STATUS_INTERVAL_MS));
    }
}

static void load_device_config(void)
{
    if (web_config_load(&s_device_config) == ESP_OK && web_config_has_saved()) {
        ESP_LOGI(TAG, "Loaded config from NVS: SSID=%s, Broker=%s",
                 s_device_config.wifi_ssid, s_device_config.mqtt_broker);
    } else {
        ESP_LOGI(TAG, "No saved config, using defaults from menuconfig");
        strncpy(s_device_config.wifi_ssid, DEFAULT_WIFI_SSID, sizeof(s_device_config.wifi_ssid) - 1);
        strncpy(s_device_config.wifi_pass, DEFAULT_WIFI_PASS, sizeof(s_device_config.wifi_pass) - 1);
        strncpy(s_device_config.mqtt_broker, DEFAULT_MQTT_BROKER, sizeof(s_device_config.mqtt_broker) - 1);
        strncpy(s_device_config.mqtt_client, DEFAULT_MQTT_CLIENT_ID, sizeof(s_device_config.mqtt_client) - 1);
        web_config_save(&s_device_config);
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "LuomiNest ESP32-S3 starting...");

#if CONFIG_LN_ENABLE_WATCHDOG
    esp_task_wdt_config_t wdt_config = {
        .timeout_ms = CONFIG_LN_WATCHDOG_TIMEOUT_SEC * 1000,
        .idle_core_mask = 0,
        .trigger_panic = true,
    };
    esp_task_wdt_deinit();
    ESP_ERROR_CHECK(esp_task_wdt_init(&wdt_config));
    ESP_LOGI(TAG, "Watchdog enabled (timeout=%ds)", CONFIG_LN_WATCHDOG_TIMEOUT_SEC);
#endif

    st7735s_config_t lcd_cfg = {
        .spi_host = ST7735S_SPI_HOST,
        .clk_pin = ST7735S_CLK_PIN,
        .mosi_pin = ST7735S_MOSI_PIN,
        .dc_pin = ST7735S_DC_PIN,
        .rst_pin = ST7735S_RST_PIN,
        .cs_pin = ST7735S_CS_PIN,
        .bl_pin = ST7735S_BL_PIN,
        .width = ST7735S_WIDTH,
        .height = ST7735S_HEIGHT,
        .spi_freq = ST7735S_SPI_FREQ,
        .x_offset = ST7735S_X_OFFSET,
        .y_offset = ST7735S_Y_OFFSET,
        .madctl = ST7735S_MADCTL,
    };

    ESP_ERROR_CHECK(st7735s_init(&lcd_cfg, &s_lcd));

    ESP_ERROR_CHECK(lvgl_port_init(&s_lcd, &s_lvgl_port));
    ESP_ERROR_CHECK(avatar_engine_init(s_lvgl_port.screen, &s_lcd));

    s_frame_queue = xQueueCreate(FRAME_QUEUE_LEN, sizeof(frame_msg_t));

    xTaskCreatePinnedToCore(lvgl_task, "lvgl", 8192, NULL, 5, NULL, 0);
    xTaskCreatePinnedToCore(frame_decode_task, "frame_dec", 16384, NULL, 4, NULL, 1);

    wifi_mgr_register_connected_cb(on_wifi_connected);
    wifi_mgr_register_disconnected_cb(on_wifi_disconnected);
    wifi_mgr_init();

    load_device_config();

    ESP_LOGI(TAG, "WiFi SSID: %s", s_device_config.wifi_ssid);
    ESP_LOGI(TAG, "MQTT Broker: %s", s_device_config.mqtt_broker[0] ? s_device_config.mqtt_broker : DEFAULT_MQTT_BROKER);

    esp_err_t wifi_result = wifi_mgr_connect(s_device_config.wifi_ssid, s_device_config.wifi_pass);

    if (wifi_result != ESP_OK) {
        ESP_LOGW(TAG, "WiFi connection failed, starting AP config portal...");
        web_config_start_ap();
    } else {
        xTaskCreatePinnedToCore(status_task, "status", 4096, NULL, 2, NULL, 0);
    }

    ESP_LOGI(TAG, "LuomiNest ESP32-S3 ready! (heap=%u, psram=%u)",
             (unsigned)esp_get_free_heap_size(),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
}
