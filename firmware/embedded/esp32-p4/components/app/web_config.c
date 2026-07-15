/**
 * LuomiNest P4 - NVS 配置存储 + Web AP 配置门户
 * 从旧 esp32-p4/main/web_config.c 移植
 *
 * NVS 部分: 独立于网络, 可直接使用
 * AP/HTTP 部分: 需要 WiFi (P4 无 C6 时不可用, 返回 ESP_ERR_NOT_SUPPORTED)
 *
 * 设计选择 (KISS):
 *   - NVS 只存 6 个字段, 不做 schema 版本管理
 *   - AP 模式用 esp_http_server + DNS 劫持实现 captive portal
 *   - P4 无 WiFi 硬件时 AP 相关函数优雅降级
 */

#include "web_config.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

static const char *TAG = "web_config";

/* === NVS 配置存储 (无网络依赖) === */

esp_err_t web_config_load(ln_config_t *cfg)
{
    if (!cfg) return ESP_ERR_INVALID_ARG;

    nvs_handle_t handle;
    esp_err_t err = nvs_open(LN_NVS_NAMESPACE, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        memset(cfg, 0, sizeof(ln_config_t));
        return err;
    }

    size_t len;
    int32_t val;
    len = sizeof(cfg->wifi_ssid);  nvs_get_str(handle, LN_NVS_KEY_WIFI_SSID,  cfg->wifi_ssid,  &len);
    len = sizeof(cfg->wifi_pass);  nvs_get_str(handle, LN_NVS_KEY_WIFI_PASS,  cfg->wifi_pass,  &len);
    len = sizeof(cfg->mqtt_broker); nvs_get_str(handle, LN_NVS_KEY_MQTT_BROKER, cfg->mqtt_broker, &len);
    len = sizeof(cfg->mqtt_client); nvs_get_str(handle, LN_NVS_KEY_MQTT_CLIENT, cfg->mqtt_client, &len);
    if (nvs_get_i32(handle, LN_NVS_KEY_BRIGHTNESS, &val) == ESP_OK) cfg->brightness = val; else cfg->brightness = 80;
    if (nvs_get_i32(handle, LN_NVS_KEY_VOLUME, &val) == ESP_OK) cfg->volume = val; else cfg->volume = 50;

    nvs_close(handle);
    return ESP_OK;
}

esp_err_t web_config_save(const ln_config_t *cfg)
{
    if (!cfg) return ESP_ERR_INVALID_ARG;

    nvs_handle_t handle;
    esp_err_t err = nvs_open(LN_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (err != ESP_OK) return err;

    #define NVS_CHECK(expr) do { err = (expr); if (err != ESP_OK) { nvs_close(handle); return err; } } while(0)

    if (cfg->wifi_ssid[0])  NVS_CHECK(nvs_set_str(handle, LN_NVS_KEY_WIFI_SSID,  cfg->wifi_ssid));
    if (cfg->wifi_pass[0])  NVS_CHECK(nvs_set_str(handle, LN_NVS_KEY_WIFI_PASS,  cfg->wifi_pass));
    if (cfg->mqtt_broker[0]) NVS_CHECK(nvs_set_str(handle, LN_NVS_KEY_MQTT_BROKER, cfg->mqtt_broker));
    if (cfg->mqtt_client[0]) NVS_CHECK(nvs_set_str(handle, LN_NVS_KEY_MQTT_CLIENT, cfg->mqtt_client));
    NVS_CHECK(nvs_set_i32(handle, LN_NVS_KEY_BRIGHTNESS, cfg->brightness));
    NVS_CHECK(nvs_set_i32(handle, LN_NVS_KEY_VOLUME, cfg->volume));
    NVS_CHECK(nvs_commit(handle));

    #undef NVS_CHECK

    nvs_close(handle);
    ESP_LOGI(TAG, "Config saved: SSID=%s, Broker=%s, Brightness=%d",
             cfg->wifi_ssid, cfg->mqtt_broker, cfg->brightness);
    return ESP_OK;
}

bool web_config_has_saved(void)
{
    nvs_handle_t handle;
    if (nvs_open(LN_NVS_NAMESPACE, NVS_READONLY, &handle) != ESP_OK) return false;
    size_t len = 0;
    esp_err_t err = nvs_get_str(handle, LN_NVS_KEY_WIFI_SSID, NULL, &len);
    nvs_close(handle);
    return (err == ESP_OK && len > 1);
}

/* === AP 模式配网门户 (需要 WiFi, P4 无 C6 时不可用) === */

#if CONFIG_ESP_WIFI_ENABLED

#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_http_server.h"
#include "cJSON.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"

#define AP_SSID_PREFIX  "LuomiNest-P4-"
#define AP_PASSWORD     "luominest"
#define AP_CHANNEL      1
#define AP_MAX_CONN     4
#define DNS_PORT        53
#define AP_IP_ADDR      "192.168.4.1"

static httpd_handle_t s_server = NULL;
static bool s_ap_active = false;
static int s_dns_socket = -1;
static TaskHandle_t s_dns_task_handle = NULL;

static const char HTML_PAGE[] =
"<!DOCTYPE html>"
"<html lang='zh-CN'>"
"<head>"
"<meta charset='UTF-8'>"
"<meta name='viewport' content='width=device-width,initial-scale=1'>"
"<title>LuomiNest P4</title>"
"<style>"
"*{margin:0;padding:0;box-sizing:border-box}"
"body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
"background:#f0f2f5;min-height:100vh;display:flex;align-items:center;justify-content:center}"
".card{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.1);"
"width:90%;max-width:420px;padding:32px 24px}"
"h1{font-size:22px;color:#1a1a1a;text-align:center;margin-bottom:4px}"
".sub{font-size:13px;color:#888;text-align:center;margin-bottom:24px}"
".form-group{margin-bottom:16px}"
"label{display:block;font-size:13px;color:#555;margin-bottom:6px}"
"input{width:100%;padding:10px 12px;border:1px solid #d9d9d9;border-radius:8px;"
"font-size:14px;outline:none}"
"input:focus{border-color:#1677ff}"
".btn{width:100%;padding:12px;background:#1677ff;color:#fff;border:none;border-radius:8px;"
"font-size:15px;cursor:pointer;margin-top:8px}"
".btn:hover{background:#0958d9}"
".status{margin-top:12px;padding:10px;border-radius:8px;font-size:13px;text-align:center}"
".status.success{background:#f6ffed;color:#52c41a}"
".status.error{background:#fff2f0;color:#ff4d4f}"
"</style>"
"</head>"
"<body>"
"<div class='card'>"
"<h1>LuomiNest P4</h1>"
"<p class='sub'>WiFi Configuration</p>"
"<div class='form-group'><label>SSID</label>"
"<input id='ssid' placeholder='WiFi SSID'></div>"
"<div class='form-group'><label>Password</label>"
"<input id='pass' type='password' placeholder='WiFi password'></div>"
"<button class='btn' onclick='save()'>Save & Restart</button>"
"<div id='status'></div>"
"</div>"
"<script>"
"function save(){"
"var ssid=document.getElementById('ssid').value;"
"var pass=document.getElementById('pass').value;"
"if(!ssid){document.getElementById('status').innerHTML="
"'<div class=\"status error\">Please enter SSID</div>';return}"
"fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},"
"body:JSON.stringify({wifi_ssid:ssid,wifi_pass:pass})})"
".then(r=>r.json()).then(d=>{"
"if(d.ok){document.getElementById('status').innerHTML="
"'<div class=\"status success\">Saved! Restarting...</div>';"
"setTimeout(function(){fetch('/api/restart',{method:'POST'})},1500)}"
"else document.getElementById('status').innerHTML="
"'<div class=\"status error\">Save failed</div>'"
"}).catch(e=>document.getElementById('status').innerHTML="
"'<div class=\"status error\">Network error</div>')}"
"</script>"
"</body>"
"</html>";

static esp_err_t handle_root(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, HTML_PAGE, strlen(HTML_PAGE));
    return ESP_OK;
}

static esp_err_t handle_config(httpd_req_t *req)
{
    char buf[512] = {0};
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) { httpd_resp_send_500(req); return ESP_FAIL; }
    buf[ret] = '\0';

    cJSON *root = cJSON_Parse(buf);
    if (!root) {
        httpd_resp_set_type(req, "application/json");
        httpd_resp_sendstr(req, "{\"ok\":false,\"error\":\"Invalid JSON\"}");
        return ESP_FAIL;
    }

    ln_config_t cfg = {0};
    web_config_load(&cfg);

    cJSON *item = NULL;
    item = cJSON_GetObjectItem(root, "wifi_ssid");
    if (item && cJSON_IsString(item)) {
        strncpy(cfg.wifi_ssid, item->valuestring, LN_MAX_SSID_LEN - 1);
        cfg.wifi_ssid[LN_MAX_SSID_LEN - 1] = '\0';
    }
    item = cJSON_GetObjectItem(root, "wifi_pass");
    if (item && cJSON_IsString(item)) {
        strncpy(cfg.wifi_pass, item->valuestring, LN_MAX_PASS_LEN - 1);
        cfg.wifi_pass[LN_MAX_PASS_LEN - 1] = '\0';
    }
    item = cJSON_GetObjectItem(root, "mqtt_broker");
    if (item && cJSON_IsString(item)) {
        strncpy(cfg.mqtt_broker, item->valuestring, LN_MAX_BROKER_LEN - 1);
        cfg.mqtt_broker[LN_MAX_BROKER_LEN - 1] = '\0';
    }
    item = cJSON_GetObjectItem(root, "mqtt_client");
    if (item && cJSON_IsString(item)) {
        strncpy(cfg.mqtt_client, item->valuestring, LN_MAX_CLIENT_LEN - 1);
        cfg.mqtt_client[LN_MAX_CLIENT_LEN - 1] = '\0';
    }

    cJSON_Delete(root);

    esp_err_t err = web_config_save(&cfg);
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, err == ESP_OK ? "{\"ok\":true}" : "{\"ok\":false,\"error\":\"NVS write failed\"}");
    return ESP_OK;
}

static esp_err_t handle_restart(httpd_req_t *req)
{
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, "{\"ok\":true}");
    vTaskDelay(pdMS_TO_TICKS(500));
    esp_restart();
    return ESP_OK;
}

static httpd_handle_t start_webserver(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.max_uri_handlers = 8;
    config.stack_size = 8192;
    if (httpd_start(&s_server, &config) == ESP_OK) {
        httpd_uri_t u_root    = { .uri = "/",            .method = HTTP_GET,  .handler = handle_root };
        httpd_uri_t u_config  = { .uri = "/api/config",  .method = HTTP_POST, .handler = handle_config };
        httpd_uri_t u_restart = { .uri = "/api/restart",  .method = HTTP_POST, .handler = handle_restart };
        httpd_register_uri_handler(s_server, &u_root);
        httpd_register_uri_handler(s_server, &u_config);
        httpd_register_uri_handler(s_server, &u_restart);
        ESP_LOGI(TAG, "Web server started");
        return s_server;
    }
    return NULL;
}

static void dns_task(void *pvParameters)
{
    char rx_buffer[128];
    struct sockaddr_in source_addr;
    socklen_t socklen = sizeof(source_addr);
    while (1) {
        int len = recvfrom(s_dns_socket, rx_buffer, sizeof(rx_buffer), 0,
                           (struct sockaddr *)&source_addr, &socklen);
        if (len < 12) continue;
        uint8_t resp[256];
        memcpy(resp, rx_buffer, len);
        resp[2] = 0x81; resp[3] = 0x80;
        resp[6] = resp[4]; resp[7] = resp[5];
        int pos = len;
        resp[pos++] = 0xC0; resp[pos++] = 0x0C;
        resp[pos++] = 0x00; resp[pos++] = 0x01;
        resp[pos++] = 0x00; resp[pos++] = 0x01;
        resp[pos++] = 0x00; resp[pos++] = 0x00;
        resp[pos++] = 0x00; resp[pos++] = 0x3C;
        resp[pos++] = 0x00; resp[pos++] = 0x04;
        uint32_t ip = ipaddr_addr(AP_IP_ADDR);
        resp[pos++] = (ip >> 0) & 0xFF;
        resp[pos++] = (ip >> 8) & 0xFF;
        resp[pos++] = (ip >> 16) & 0xFF;
        resp[pos++] = (ip >> 24) & 0xFF;
        sendto(s_dns_socket, resp, pos, 0, (struct sockaddr *)&source_addr, socklen);
    }
}

esp_err_t web_config_start_ap(void)
{
    if (s_ap_active) return ESP_OK;
    ESP_LOGI(TAG, "Starting AP mode for configuration...");
    esp_netif_create_default_wifi_ap();
    uint8_t mac[6];
    esp_wifi_get_mac(WIFI_IF_STA, mac);
    char ap_ssid[32];
    snprintf(ap_ssid, sizeof(ap_ssid), AP_SSID_PREFIX "%02X%02X%02X", mac[3], mac[4], mac[5]);
    wifi_config_t ap_config = {0};
    snprintf((char *)ap_config.ap.ssid, sizeof(ap_config.ap.ssid), "%s", ap_ssid);
    snprintf((char *)ap_config.ap.password, sizeof(ap_config.ap.password), "%s", AP_PASSWORD);
    ap_config.ap.channel = AP_CHANNEL;
    ap_config.ap.max_connection = AP_MAX_CONN;
    ap_config.ap.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(DNS_PORT);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    s_dns_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (s_dns_socket >= 0 && bind(s_dns_socket, (struct sockaddr *)&addr, sizeof(addr)) >= 0) {
        xTaskCreate(dns_task, "dns_server", 4096, NULL, 3, &s_dns_task_handle);
    }

    start_webserver();
    s_ap_active = true;
    ESP_LOGI(TAG, "AP started: SSID=%s, IP=%s", ap_ssid, AP_IP_ADDR);
    return ESP_OK;
}

esp_err_t web_config_stop_ap(void)
{
    if (!s_ap_active) return ESP_OK;
    if (s_server) { httpd_stop(s_server); s_server = NULL; }
    if (s_dns_task_handle) { vTaskDelete(s_dns_task_handle); s_dns_task_handle = NULL; }
    if (s_dns_socket >= 0) { close(s_dns_socket); s_dns_socket = -1; }
    esp_wifi_stop();
    s_ap_active = false;
    return ESP_OK;
}

bool web_config_is_ap_active(void) { return s_ap_active; }

#else /* !CONFIG_ESP_WIFI_ENABLED */

esp_err_t web_config_start_ap(void)
{
    ESP_LOGW(TAG, "AP mode not available (WiFi disabled, P4 without C6)");
    return ESP_ERR_NOT_SUPPORTED;
}

esp_err_t web_config_stop_ap(void) { return ESP_OK; }
bool web_config_is_ap_active(void) { return false; }

#endif /* CONFIG_ESP_WIFI_ENABLED */
