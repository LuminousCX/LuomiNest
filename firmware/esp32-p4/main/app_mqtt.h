#ifndef APP_MQTT_H
#define APP_MQTT_H

#include "esp_err.h"
#include <stdbool.h>

typedef enum {
    MQTT_STATE_DISCONNECTED = 0,
    MQTT_STATE_CONNECTING,
    MQTT_STATE_CONNECTED,
} mqtt_state_t;

typedef void (*mqtt_message_cb_t)(const char *topic, const char *data, int data_len);
typedef void (*mqtt_stream_cb_t)(const char *topic, const uint8_t *data, int data_len);
typedef void (*mqtt_connected_cb_t)(void);
typedef void (*mqtt_disconnected_cb_t)(void);

esp_err_t app_mqtt_init(const char *broker_uri, const char *client_id);
esp_err_t app_mqtt_subscribe(const char *topic, int qos);
esp_err_t app_mqtt_publish(const char *topic, const char *data, int len, int qos);
esp_err_t app_mqtt_register_message_cb(mqtt_message_cb_t cb);
esp_err_t app_mqtt_register_stream_cb(mqtt_stream_cb_t cb);
esp_err_t app_mqtt_register_connected_cb(mqtt_connected_cb_t cb);
esp_err_t app_mqtt_register_disconnected_cb(mqtt_disconnected_cb_t cb);
bool app_mqtt_is_connected(void);
mqtt_state_t app_mqtt_get_state(void);

#endif
