#include "app_mqtt.h"
#include "mqtt_client.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include <string.h>
#include <stdlib.h>

static const char *TAG = "mqtt";

static esp_mqtt_client_handle_t s_client = NULL;
static mqtt_message_cb_t s_msg_cb = NULL;
static mqtt_stream_cb_t s_stream_cb = NULL;
static mqtt_connected_cb_t s_conn_cb = NULL;
static mqtt_disconnected_cb_t s_disc_cb = NULL;
static mqtt_state_t s_state = MQTT_STATE_DISCONNECTED;
static int s_backoff_ms = 1000;
static int s_reconnect_count = 0;
static char s_status_topic[128] = {0};

#define INITIAL_BACKOFF_MS  1000
#define MAX_BACKOFF_MS      CONFIG_LN_MQTT_RECONNECT_MAX_MS

static uint8_t *s_stream_buf = NULL;
static uint32_t s_stream_buf_len = 0;
static uint32_t s_stream_buf_cap = 0;
static char s_stream_topic[128] = {0};
#define STREAM_BUF_INITIAL_CAP (200 * 1024)

static uint32_t s_stream_rx_count = 0;
static uint32_t s_stream_rx_bytes = 0;

static void stream_buf_reset(void)
{
    s_stream_buf_len = 0;
    s_stream_topic[0] = '\0';
}

static void stream_buf_ensure(uint32_t needed)
{
    if (s_stream_buf_cap >= needed) return;
    uint32_t new_cap = s_stream_buf_cap == 0 ? STREAM_BUF_INITIAL_CAP : s_stream_buf_cap;
    while (new_cap < needed) new_cap *= 2;
    ESP_LOGI(TAG, "Stream buffer realloc: %u -> %u bytes (free PSRAM=%u)",
             (unsigned)s_stream_buf_cap, (unsigned)new_cap,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    uint8_t *new_buf = heap_caps_realloc(s_stream_buf, new_cap, MALLOC_CAP_SPIRAM);
    if (!new_buf) {
        ESP_LOGE(TAG, "!! Stream buffer realloc FAILED (%u bytes, free PSRAM=%u)",
                 new_cap, (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
        stream_buf_reset();
        free(s_stream_buf);
        s_stream_buf = NULL;
        s_stream_buf_cap = 0;
        return;
    }
    s_stream_buf = new_buf;
    s_stream_buf_cap = new_cap;
}

static void mqtt_event_handler(void *handler_args, esp_event_base_t base,
                                int32_t event_id, void *event_data)
{
    (void)handler_args;
    (void)base;
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "MQTT connected");
        s_state = MQTT_STATE_CONNECTED;
        s_backoff_ms = INITIAL_BACKOFF_MS;
        s_reconnect_count = 0;
        s_stream_rx_count = 0;
        s_stream_rx_bytes = 0;
        if (s_conn_cb) s_conn_cb();
        break;

    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "MQTT disconnected (reconnect #%d, backoff %d ms, streams_rx=%u)",
                 s_reconnect_count, s_backoff_ms, (unsigned)s_stream_rx_count);
        s_state = MQTT_STATE_DISCONNECTED;
        if (s_disc_cb) s_disc_cb();
        s_reconnect_count++;
        s_backoff_ms = s_backoff_ms * 2;
        if (s_backoff_ms > MAX_BACKOFF_MS) {
            s_backoff_ms = MAX_BACKOFF_MS;
        }
        stream_buf_reset();
        break;

    case MQTT_EVENT_DATA:
    {
        if (event->data_len <= 0) break;

        bool is_stream = (s_stream_cb != NULL && event->total_data_len > 256);

        if (is_stream) {
            if (event->current_data_offset == 0) {
                stream_buf_reset();
                int topic_len = event->topic_len < (int)(sizeof(s_stream_topic) - 1) ?
                                event->topic_len : (int)(sizeof(s_stream_topic) - 1);
                memcpy(s_stream_topic, event->topic, topic_len);
                s_stream_topic[topic_len] = '\0';
                ESP_LOGD(TAG, "Stream START: topic=%s, total=%u",
                         s_stream_topic, (unsigned)event->total_data_len);
            }

            stream_buf_ensure(event->total_data_len);
            if (!s_stream_buf) {
                ESP_LOGE(TAG, "!! Stream buffer NULL, dropping chunk (offset=%u, len=%u)",
                         (unsigned)event->current_data_offset, (unsigned)event->data_len);
                break;
            }

            memcpy(s_stream_buf + s_stream_buf_len, event->data, event->data_len);
            s_stream_buf_len += event->data_len;

            ESP_LOGD(TAG, ">> Stream chunk: offset=%u, chunk_len=%u, buf_len=%u, total=%u",
                     (unsigned)event->current_data_offset, (unsigned)event->data_len,
                     (unsigned)s_stream_buf_len, (unsigned)event->total_data_len);

            if (s_stream_buf_len >= event->total_data_len) {
                s_stream_rx_count++;
                s_stream_rx_bytes += s_stream_buf_len;
                ESP_LOGD(TAG, "Stream COMPLETE: len=%u, frames=%u",
                         (unsigned)s_stream_buf_len, (unsigned)s_stream_rx_count);
                s_stream_cb(s_stream_topic, s_stream_buf, s_stream_buf_len);
                s_stream_buf_len = 0;
            }
        } else {
            char topic[128] = {0};
            int topic_len = event->topic_len < (int)(sizeof(topic) - 1) ?
                            event->topic_len : (int)(sizeof(topic) - 1);
            memcpy(topic, event->topic, topic_len);

            ESP_LOGD(TAG, "MQTT msg: topic=%s, len=%d", topic, event->data_len);

            if (s_msg_cb) {
                char *data = malloc(event->data_len + 1);
                if (data) {
                    memcpy(data, event->data, event->data_len);
                    data[event->data_len] = '\0';
                    s_msg_cb(topic, data, event->data_len);
                    free(data);
                }
            }
        }
        break;
    }

    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "MQTT error: last errno=%d, err_type=%d",
                 event->error_handle->esp_tls_last_esp_err,
                 event->error_handle->error_type);
        break;

    case MQTT_EVENT_BEFORE_CONNECT:
        ESP_LOGI(TAG, "MQTT connecting...");
        s_state = MQTT_STATE_CONNECTING;
        break;

    default:
        break;
    }
}

esp_err_t app_mqtt_init(const char *broker_uri, const char *client_id)
{
    snprintf(s_status_topic, sizeof(s_status_topic), "luominest/p4/status");

    ESP_LOGI(TAG, "MQTT init: broker=%s, client_id=%s, buffer=131072", broker_uri, client_id);

    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = broker_uri,
        .credentials.client_id = client_id,
        .buffer.size = 131072,
        .session.last_will = {
            .topic = s_status_topic,
            .msg = "{\"state\":\"offline\"}",
            .msg_len = 0,
            .qos = 1,
            .retain = true,
        },
        .session.keepalive = 30,
        .network.reconnect_timeout_ms = s_backoff_ms,
        .network.timeout_ms = 10000,
    };

    s_client = esp_mqtt_client_init(&cfg);
    if (!s_client) {
        ESP_LOGE(TAG, "Failed to init MQTT client");
        return ESP_FAIL;
    }

    esp_mqtt_client_register_event(s_client, ESP_EVENT_ANY_ID,
                                    mqtt_event_handler, NULL);
    esp_mqtt_client_start(s_client);

    s_state = MQTT_STATE_CONNECTING;
    s_backoff_ms = INITIAL_BACKOFF_MS;

    ESP_LOGI(TAG, "MQTT client initialized (%s)", broker_uri);
    return ESP_OK;
}

esp_err_t app_mqtt_subscribe(const char *topic, int qos)
{
    if (!s_client) return ESP_ERR_INVALID_STATE;
    int msg_id = esp_mqtt_client_subscribe(s_client, topic, qos);
    if (msg_id < 0) return ESP_FAIL;
    ESP_LOGI(TAG, "Subscribed to %s (msg_id=%d)", topic, msg_id);
    return ESP_OK;
}

esp_err_t app_mqtt_publish(const char *topic, const char *data, int len, int qos)
{
    if (!s_client) return ESP_ERR_INVALID_STATE;
    if (s_state != MQTT_STATE_CONNECTED) {
        ESP_LOGD(TAG, "Publish skipped: not connected");
        return ESP_ERR_INVALID_STATE;
    }
    int msg_id = esp_mqtt_client_publish(s_client, topic, data, len, qos, 0);
    if (msg_id < 0) return ESP_FAIL;
    return ESP_OK;
}

esp_err_t app_mqtt_register_message_cb(mqtt_message_cb_t cb)
{
    s_msg_cb = cb;
    return ESP_OK;
}

esp_err_t app_mqtt_register_stream_cb(mqtt_stream_cb_t cb)
{
    s_stream_cb = cb;
    return ESP_OK;
}

esp_err_t app_mqtt_register_connected_cb(mqtt_connected_cb_t cb)
{
    s_conn_cb = cb;
    return ESP_OK;
}

esp_err_t app_mqtt_register_disconnected_cb(mqtt_disconnected_cb_t cb)
{
    s_disc_cb = cb;
    return ESP_OK;
}

bool app_mqtt_is_connected(void)
{
    return s_state == MQTT_STATE_CONNECTED;
}

mqtt_state_t app_mqtt_get_state(void)
{
    return s_state;
}
