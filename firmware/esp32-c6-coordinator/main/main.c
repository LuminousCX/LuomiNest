#include <string.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "driver/spi_slave.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

static const char *TAG = "c6_coord";

#define SPI_FRAME_HEADER_SIZE 8
#define SPI_FRAME_MAGIC_0 0xAA
#define SPI_FRAME_MAGIC_1 0x55

#define WIFI_SSID      CONFIG_C6_WIFI_SSID
#define WIFI_PASS      CONFIG_C6_WIFI_PASSWORD
#define MQTT_BROKER    CONFIG_C6_MQTT_BROKER

#define TOPIC_STREAM   "luominest/p4/stream"

#define SPI_CLK_PIN    GPIO_NUM_2
#define SPI_MOSI_PIN   GPIO_NUM_3
#define SPI_MISO_PIN   GPIO_NUM_4
#define SPI_CS_PIN     GPIO_NUM_5

#define SPI_BUF_SIZE   4096

static esp_mqtt_client_handle_t s_mqtt = NULL;
static bool s_mqtt_connected = false;
static bool s_wifi_connected = false;

static uint8_t *s_spi_send_buf = NULL;
static uint8_t *s_spi_recv_buf = NULL;
static SemaphoreHandle_t s_spi_done_sem = NULL;
static volatile bool s_spi_ready = false;

static QueueHandle_t s_frame_queue = NULL;

typedef struct {
    uint8_t *data;
    uint32_t len;
} frame_msg_t;

#define FRAME_QUEUE_LEN 4

static uint16_t crc16_ccitt(const uint8_t *data, uint32_t len)
{
    uint16_t crc = 0;
    for (uint32_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int j = 0; j < 8; j++) {
            if (crc & 0x8000) {
                crc = (crc << 1) ^ 0x1021;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

static void spi_post_setup_cb(spi_slave_transaction_t *trans)
{
    (void)trans;
}

static void spi_post_trans_cb(spi_slave_transaction_t *trans)
{
    (void)trans;
    if (s_spi_done_sem) {
        xSemaphoreGiveFromISR(s_spi_done_sem, NULL);
    }
}

static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                                int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "WiFi disconnected, reconnecting...");
        s_wifi_connected = false;
        vTaskDelay(pdMS_TO_TICKS(2000));
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
        s_wifi_connected = true;
    }
}

static void mqtt_event_handler(void *arg, esp_event_base_t event_base,
                                int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;
    if (event_id == MQTT_EVENT_CONNECTED) {
        ESP_LOGI(TAG, "MQTT connected");
        s_mqtt_connected = true;
        esp_mqtt_client_subscribe(s_mqtt, TOPIC_STREAM, 0);
    } else if (event_id == MQTT_EVENT_DISCONNECTED) {
        ESP_LOGW(TAG, "MQTT disconnected");
        s_mqtt_connected = false;
    } else if (event_id == MQTT_EVENT_DATA) {
        if (strncmp(event->topic, TOPIC_STREAM, event->topic_len) == 0) {
            frame_msg_t msg = {0};
            msg.len = event->data_len;
            msg.data = malloc(msg.len);
            if (msg.data) {
                memcpy(msg.data, event->data, msg.len);
                frame_msg_t discarded = {0};
                if (xQueueSend(s_frame_queue, &msg, 0) != pdTRUE) {
                    if (xQueueReceive(s_frame_queue, &discarded, 0) == pdTRUE) {
                        free(discarded.data);
                    }
                    xQueueSend(s_frame_queue, &msg, 0);
                }
            }
        }
    }
}

static void init_wifi(void)
{
    esp_netif_init();
    esp_event_loop_create_default();
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);

    esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, NULL);
    esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, NULL);

    wifi_config_t wifi_config = {};
    strncpy((char *)wifi_config.sta.ssid, WIFI_SSID, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char *)wifi_config.sta.password, WIFI_PASS, sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_set_config(WIFI_IF_STA, &wifi_config);
    esp_wifi_start();

    ESP_LOGI(TAG, "WiFi connecting to %s...", WIFI_SSID);
}

static void init_mqtt(void)
{
    esp_mqtt_client_config_t cfg = {
        .broker.uri = MQTT_BROKER,
    };
    s_mqtt = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_register_event(s_mqtt, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL);
    esp_mqtt_client_start(s_mqtt);
}

static void init_spi_slave(void)
{
    s_spi_done_sem = xSemaphoreCreateBinary();

    spi_bus_config_t bus_cfg = {
        .mosi_io_num = SPI_MOSI_PIN,
        .miso_io_num = SPI_MISO_PIN,
        .sclk_io_num = SPI_CLK_PIN,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = SPI_BUF_SIZE,
    };

    spi_slave_interface_config_t slv_cfg = {
        .mode = 0,
        .spics_io_num = SPI_CS_PIN,
        .queue_size = 4,
        .flags = 0,
        .post_setup_cb = spi_post_setup_cb,
        .post_trans_cb = spi_post_trans_cb,
    };

    ESP_ERROR_CHECK(spi_slave_initialize(SPI2_HOST, &bus_cfg, &slv_cfg, SPI_DMA_CH_AUTO));

    s_spi_send_buf = heap_caps_malloc(SPI_BUF_SIZE, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);
    s_spi_recv_buf = heap_caps_malloc(SPI_BUF_SIZE, MALLOC_CAP_DMA | MALLOC_CAP_8BIT);

    s_spi_ready = true;
    ESP_LOGI(TAG, "SPI Slave ready (CLK=%d, MOSI=%d, MISO=%d, CS=%d)",
             SPI_CLK_PIN, SPI_MOSI_PIN, SPI_MISO_PIN, SPI_CS_PIN);
}

static void spi_send_frame(const uint8_t *data, uint32_t len)
{
    if (!s_spi_ready || !s_spi_send_buf) return;

    uint16_t crc = crc16_ccitt(data, len);

    uint8_t header[SPI_FRAME_HEADER_SIZE];
    header[0] = SPI_FRAME_MAGIC_0;
    header[1] = SPI_FRAME_MAGIC_1;
    header[2] = (len >> 24) & 0xFF;
    header[3] = (len >> 16) & 0xFF;
    header[4] = (len >> 8) & 0xFF;
    header[5] = len & 0xFF;
    header[6] = (crc >> 8) & 0xFF;
    header[7] = crc & 0xFF;

    spi_slave_transaction_t trans = {
        .tx_buffer = header,
        .rx_buffer = s_spi_recv_buf,
        .length = SPI_FRAME_HEADER_SIZE * 8,
    };
    spi_slave_transmit(SPI2_HOST, &trans, pdMS_TO_TICKS(100));

    uint32_t offset = 0;
    while (offset < len) {
        uint32_t chunk = len - offset;
        if (chunk > SPI_BUF_SIZE) chunk = SPI_BUF_SIZE;

        memcpy(s_spi_send_buf, data + offset, chunk);

        trans.tx_buffer = s_spi_send_buf;
        trans.rx_buffer = s_spi_recv_buf;
        trans.length = chunk * 8;
        spi_slave_transmit(SPI2_HOST, &trans, pdMS_TO_TICKS(500));

        offset += chunk;
    }
}

static void frame_forward_task(void *pvParameter)
{
    frame_msg_t msg = {0};
    while (1) {
        if (xQueueReceive(s_frame_queue, &msg, pdMS_TO_TICKS(1000)) == pdTRUE) {
            spi_send_frame(msg.data, msg.len);
            free(msg.data);
            msg.data = NULL;
        }
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "=== LuomiNest C6 Coordinator ===");

    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }

    s_frame_queue = xQueueCreate(FRAME_QUEUE_LEN, sizeof(frame_msg_t));

    init_wifi();

    int retry = 0;
    while (!s_wifi_connected && retry < 30) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        retry++;
    }

    if (s_wifi_connected) {
        init_mqtt();
    } else {
        ESP_LOGE(TAG, "WiFi failed, cannot start MQTT");
    }

    init_spi_slave();

    xTaskCreatePinnedToCore(frame_forward_task, "fwd", 8192, NULL, 4, NULL, 0);

    ESP_LOGI(TAG, "C6 Coordinator ready! Free heap: %u",
             (unsigned)esp_get_free_heap_size());
}
