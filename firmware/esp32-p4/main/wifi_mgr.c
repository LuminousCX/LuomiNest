#include "wifi_mgr.h"
#include "web_config.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"

#if CONFIG_IDF_TARGET_ESP32P4
#include "esp_wifi_remote.h"
#endif

static const char *TAG = "wifi_mgr";

#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT      BIT1

#define INITIAL_BACKOFF_MS  500
#define MAX_BACKOFF_MS      CONFIG_LN_WIFI_RECONNECT_MAX_MS
#define MAX_RETRY_INIT      10

static EventGroupHandle_t s_wifi_event_group;
static wifi_connected_cb_t s_connected_cb = NULL;
static wifi_disconnected_cb_t s_disconnected_cb = NULL;
static int s_retry_count = 0;
static int s_backoff_ms = INITIAL_BACKOFF_MS;
static bool s_connected = false;
static bool s_initial_connect_done = false;
static bool s_initialized = false;
static char s_ip_str[16] = {0};

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                                int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        s_connected = false;
        s_ip_str[0] = '\0';
        if (s_disconnected_cb) s_disconnected_cb();

        wifi_event_sta_disconnected_t *disconn = (wifi_event_sta_disconnected_t *)event_data;
        ESP_LOGW(TAG, "WiFi disconnected (reason=%d, retry=%d)", disconn->reason, s_retry_count);

        if (!s_initial_connect_done) {
            if (s_retry_count < MAX_RETRY_INIT) {
                s_retry_count++;
                s_backoff_ms = INITIAL_BACKOFF_MS * (1 << (s_retry_count - 1));
                if (s_backoff_ms > MAX_BACKOFF_MS) s_backoff_ms = MAX_BACKOFF_MS;
                vTaskDelay(pdMS_TO_TICKS(s_backoff_ms));
                esp_wifi_connect();
            } else {
                ESP_LOGE(TAG, "Initial connection failed after %d retries", MAX_RETRY_INIT);
                xEventGroupSetBits(s_wifi_event_group, WIFI_FAIL_BIT);
            }
        } else {
            s_backoff_ms = s_backoff_ms * 2;
            if (s_backoff_ms > MAX_BACKOFF_MS) s_backoff_ms = MAX_BACKOFF_MS;
            vTaskDelay(pdMS_TO_TICKS(s_backoff_ms));
            esp_wifi_connect();
        }
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        snprintf(s_ip_str, sizeof(s_ip_str), IPSTR, IP2STR(&event->ip_info.ip));
        ESP_LOGI(TAG, "Got IP:%s", s_ip_str);
        s_retry_count = 0;
        s_backoff_ms = INITIAL_BACKOFF_MS;
        s_connected = true;
        s_initial_connect_done = true;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
        if (s_connected_cb) s_connected_cb();
    }
}

esp_err_t wifi_mgr_init(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "NVS init failed: 0x%x", ret);
        return ret;
    }

    s_wifi_event_group = xEventGroupCreate();

    ret = esp_netif_init();
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(TAG, "Netif init failed: 0x%x", ret);
        return ret;
    }

    ret = esp_event_loop_create_default();
    if (ret != ESP_OK && ret != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(TAG, "Event loop create failed: 0x%x", ret);
        return ret;
    }

    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t inst_any_id;
    esp_event_handler_instance_t inst_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT,
                                                         ESP_EVENT_ANY_ID,
                                                         &wifi_event_handler,
                                                         NULL,
                                                         &inst_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT,
                                                         IP_EVENT_STA_GOT_IP,
                                                         &wifi_event_handler,
                                                         NULL,
                                                         &inst_got_ip));

    s_initialized = true;
    ESP_LOGI(TAG, "WiFi manager initialized (ESP-Hosted via C6)");
    return ESP_OK;
}

esp_err_t wifi_mgr_connect(const char *ssid, const char *password)
{
    if (!s_initialized) return ESP_ERR_INVALID_STATE;

    s_retry_count = 0;
    s_backoff_ms = INITIAL_BACKOFF_MS;
    s_initial_connect_done = false;
    s_connected = false;

    xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT | WIFI_FAIL_BIT);

    wifi_config_t wifi_config = {};
    strncpy((char *)wifi_config.sta.ssid, ssid, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, password, sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "Connecting to %s...", ssid);

    EventBits_t bits = xEventGroupWaitBits(s_wifi_event_group,
                                            WIFI_CONNECTED_BIT | WIFI_FAIL_BIT,
                                            pdFALSE, pdFALSE,
                                            pdMS_TO_TICKS(30000));

    if (bits & WIFI_CONNECTED_BIT) {
        ESP_LOGI(TAG, "Connected to AP SSID:%s", ssid);
        return ESP_OK;
    } else {
        ESP_LOGE(TAG, "Failed to connect to SSID:%s", ssid);
        s_initial_connect_done = false;
        return ESP_FAIL;
    }
}

int8_t wifi_mgr_get_rssi(void)
{
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
        return ap.rssi;
    }
    return -127;
}

esp_err_t wifi_mgr_register_connected_cb(wifi_connected_cb_t cb)
{
    s_connected_cb = cb;
    return ESP_OK;
}

esp_err_t wifi_mgr_register_disconnected_cb(wifi_disconnected_cb_t cb)
{
    s_disconnected_cb = cb;
    return ESP_OK;
}

bool wifi_mgr_is_connected(void)
{
    return s_connected;
}

void wifi_mgr_get_ip_str(char *buf, size_t buf_len)
{
    if (!buf || buf_len == 0) return;
    snprintf(buf, buf_len, "%s", s_ip_str);
}
