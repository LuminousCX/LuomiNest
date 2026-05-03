#include "app_mqtt.h"
#include "mqtt_client.h"
#include "esp_log.h"
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
#define MAX_RECONNECT_INF   -1

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
        if (s_conn_cb) s_conn_cb();
        break;

    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "MQTT disconnected (reconnect #%d, backoff %d ms)",
                 s_reconnect_count, s_backoff_ms);
        s_state = MQTT_STATE_DISCONNECTED;
        if (s_disc_cb) s_disc_cb();
        s_reconnect_count++;
        if (MAX_RECONNECT_INF < 0 || s_reconnect_count <= 100) {
            s_backoff_ms = s_backoff_ms * 2;
            if (s_backoff_ms > MAX_BACKOFF_MS) {
                s_backoff_ms = MAX_BACKOFF_MS;
            }
        }
        break;

    case MQTT_EVENT_DATA:
        if (event->data_len > 0) {
            char topic[128] = {0};
            int topic_len = event->topic_len < (int)(sizeof(topic) - 1) ?
                            event->topic_len : (int)(sizeof(topic) - 1);
            memcpy(topic, event->topic, topic_len);

            if (s_stream_cb && event->data_len > 256) {
                s_stream_cb(topic, (const uint8_t *)event->data, event->data_len);
            } else if (s_msg_cb) {
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

    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "MQTT error: last errno=%d", event->error_handle->esp_tls_last_esp_err);
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
    snprintf(s_status_topic, sizeof(s_status_topic), "luominest/s3/status");

    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = broker_uri,
        .credentials.client_id = client_id,
        .buffer.size = 65536,
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

    ESP_LOGI(TAG, "MQTT client started, connecting to %s (LWT enabled)", broker_uri);
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
