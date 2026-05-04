#include "web_config.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_http_server.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"
#include <string.h>
#include <stdlib.h>

#if CONFIG_IDF_TARGET_ESP32P4
#include "esp_wifi_remote.h"
#endif

static const char *TAG = "web_config";

#define AP_SSID_PREFIX  "LuomiNest-P4-"
#define AP_PASSWORD     CONFIG_LN_AP_PASSWORD
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
".tabs{display:flex;border-bottom:2px solid #eee;margin-bottom:20px}"
".tab{flex:1;text-align:center;padding:10px 0;cursor:pointer;font-size:14px;"
"color:#999;border-bottom:2px solid transparent;transition:all .2s ease-in-out}"
".tab.active{color:#1677ff;border-bottom-color:#1677ff}"
".form-group{margin-bottom:16px}"
"label{display:block;font-size:13px;color:#555;margin-bottom:6px}"
"input,select{width:100%;padding:10px 12px;border:1px solid #d9d9d9;border-radius:8px;"
"font-size:14px;outline:none;transition:border-color .2s ease-in-out}"
"input:focus,select:focus{border-color:#1677ff}"
".btn{width:100%;padding:12px;background:#1677ff;color:#fff;border:none;border-radius:8px;"
"font-size:15px;cursor:pointer;transition:background .2s ease-in-out;margin-top:8px}"
".btn:hover{background:#0958d9}"
".scan-item{display:flex;align-items:center;justify-content:space-between;"
"padding:12px;border:1px solid #eee;border-radius:8px;margin-bottom:8px;cursor:pointer;"
"transition:all .2s ease-in-out}"
".scan-item:hover{border-color:#1677ff;background:#f0f5ff}"
".scan-item .ssid{font-size:14px;color:#333}"
".scan-item .rssi{font-size:12px;color:#999}"
".status{margin-top:12px;padding:10px;border-radius:8px;font-size:13px;text-align:center;"
"transition:all .3s ease-in-out}"
".status.info{background:#e6f4ff;color:#1677ff}"
".status.success{background:#f6ffed;color:#52c41a}"
".status.error{background:#fff2f0;color:#ff4d4f}"
".spinner{display:inline-block;width:16px;height:16px;border:2px solid #fff;"
"border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;"
"vertical-align:middle;margin-right:6px}"
"@keyframes spin{to{transform:rotate(360deg)}}"
".info-row{display:flex;justify-content:space-between;padding:8px 0;"
"border-bottom:1px solid #f5f5f5;font-size:13px}"
".info-row .k{color:#888}"
".info-row .v{color:#333;font-weight:500}"
".panel{display:none}"
".panel.active{display:block}"
"</style>"
"</head>"
"<body>"
"<div class='card'>"
"<h1>LuomiNest P4</h1>"
"<p class='sub'>Device Configuration Panel</p>"
"<div class='tabs'>"
"<div class='tab active' onclick='switchTab(0)'>WiFi</div>"
"<div class='tab' onclick='switchTab(1)'>Server</div>"
"<div class='tab' onclick='switchTab(2)'>Status</div>"
"</div>"
"<div class='panel active' id='p0'>"
"<div class='form-group'><label>WiFi Network</label>"
"<div id='scanList' style='max-height:200px;overflow-y:auto'>"
"<div class='scan-item' onclick='startScan()' style='justify-content:center'>"
"<span style='color:#1677ff'>Scan for WiFi networks</span></div></div></div>"
"<div class='form-group'><label>SSID</label>"
"<input id='ssid' placeholder='Enter SSID or select from scan'></div>"
"<div class='form-group'><label>Password</label>"
"<input id='pass' type='password' placeholder='WiFi password'></div>"
"<button class='btn' onclick='saveWifi()'>Save WiFi</button>"
"<div id='wifiStatus'></div></div>"
"<div class='panel' id='p1'>"
"<div class='form-group'><label>MQTT Broker</label>"
"<input id='broker' placeholder='mqtt://192.168.1.222:1883'></div>"
"<div class='form-group'><label>Client ID</label>"
"<input id='client' placeholder='luominest_p4_01'></div>"
"<button class='btn' onclick='saveServer()'>Save Server</button>"
"<div id='serverStatus'></div></div>"
"<div class='panel' id='p2'>"
"<div id='deviceInfo'>Loading...</div></div>"
"</div>"
"<script>"
"function switchTab(i){"
"document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('active',j===i));"
"document.querySelectorAll('.panel').forEach((p,j)=>p.classList.toggle('active',j===i));"
"if(i===2)loadStatus()}"
"function showStatus(id,msg,type){"
"document.getElementById(id).innerHTML='<div class=\"status '+type+'\">'+msg+'</div>'}"
"function startScan(){"
"document.getElementById('scanList').innerHTML="
"'<div class=\"scan-item\" style=\"justify-content:center\">"
"<span class=\"spinner\"></span>Scanning...</span></div>';"
"fetch('/api/scan').then(r=>r.json()).then(d=>{"
"var h='';d.networks.forEach(n=>{"
"h+='<div class=\"scan-item\" onclick=\"pickSsid(\\''+n.ssid+'\\')\">'"
"+'<span class=\"ssid\">'+n.ssid+'</span>'"
"+'<span>'+(n.auth>0?'&#128274; ':'')+'<span class=\"rssi\">'+n.rssi+' dBm</span></span></div>'"
"});if(!h)h='<div class=\"scan-item\" style=\"justify-content:center\">"
"<span style=\"color:#999\">No networks found</span></div>';"
"document.getElementById('scanList').innerHTML=h"
"}).catch(e=>{document.getElementById('scanList').innerHTML="
"'<div class=\"scan-item\" style=\"justify-content:center\">"
"<span style=\"color:#ff4d4f\">Scan failed</span></div>'})}"
"function pickSsid(s){document.getElementById('ssid').value=s;"
"document.getElementById('pass').focus()}"
"function saveWifi(){"
"var ssid=document.getElementById('ssid').value;"
"var pass=document.getElementById('pass').value;"
"if(!ssid){showStatus('wifiStatus','Please enter SSID','error');return}"
"showStatus('wifiStatus','<span class=\"spinner\"></span>Saving...','info');"
"fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},"
"body:JSON.stringify({wifi_ssid:ssid,wifi_pass:pass})})"
".then(r=>r.json()).then(d=>{"
"if(d.ok){showStatus('wifiStatus','Saved! Restarting...','success');"
"setTimeout(function(){fetch('/api/restart',{method:'POST'})},1500)}"
"else showStatus('wifiStatus','Save failed: '+d.error,'error')"
"}).catch(e=>showStatus('wifiStatus','Network error','error'))}"
"function saveServer(){"
"var broker=document.getElementById('broker').value;"
"var client=document.getElementById('client').value;"
"if(!broker){showStatus('serverStatus','Please enter broker address','error');return}"
"showStatus('serverStatus','<span class=\"spinner\"></span>Saving...','info');"
"fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},"
"body:JSON.stringify({mqtt_broker:broker,mqtt_client:client})})"
".then(r=>r.json()).then(d=>{"
"if(d.ok){showStatus('serverStatus','Saved! Restarting...','success');"
"setTimeout(function(){fetch('/api/restart',{method:'POST'})},1500)}"
"else showStatus('serverStatus','Save failed: '+d.error,'error')"
"}).catch(e=>showStatus('serverStatus','Network error','error'))}"
"function loadStatus(){"
"fetch('/api/status').then(r=>r.json()).then(d=>{"
"var h='<div class=\"info-row\"><span class=\"k\">Device</span>"
"<span class=\"v\">'+d.device+'</span></div>'"
"+'<div class=\"info-row\"><span class=\"k\">WiFi SSID</span>"
"<span class=\"v\">'+(d.wifi_ssid||'Not configured')+'</span></div>'"
"+'<div class=\"info-row\"><span class=\"k\">MQTT Broker</span>"
"<span class=\"v\">'+(d.mqtt_broker||'Not configured')+'</span></div>'"
"+'<div class=\"info-row\"><span class=\"k\">Free Heap</span>"
"<span class=\"v\">'+d.free_heap+' bytes</span></div>'"
"+'<div class=\"info-row\"><span class=\"k\">Free PSRAM</span>"
"<span class=\"v\">'+d.free_psram+' bytes</span></div>';"
"document.getElementById('deviceInfo').innerHTML=h;"
"document.getElementById('ssid').value=d.wifi_ssid||'';"
"document.getElementById('broker').value=d.mqtt_broker||'';"
"document.getElementById('client').value=d.mqtt_client||''"
"}).catch(e=>{document.getElementById('deviceInfo').innerHTML="
"'<div class=\"status error\">Failed to load</div>'})}"
"loadStatus()"
"</script>"
"</body>"
"</html>";

static esp_err_t handle_root(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, HTML_PAGE, strlen(HTML_PAGE));
    return ESP_OK;
}

static esp_err_t handle_status(httpd_req_t *req)
{
    ln_config_t cfg = {0};
    web_config_load(&cfg);
    char resp[512];
    snprintf(resp, sizeof(resp),
             "{\"device\":\"LuomiNest-P4\",\"wifi_ssid\":\"%s\","
             "\"mqtt_broker\":\"%s\",\"mqtt_client\":\"%s\","
             "\"free_heap\":%u,\"free_psram\":%u}",
             cfg.wifi_ssid, cfg.mqtt_broker, cfg.mqtt_client,
             (unsigned)esp_get_free_heap_size(),
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_send(req, resp, strlen(resp));
    return ESP_OK;
}

static esp_err_t handle_scan(httpd_req_t *req)
{
    wifi_scan_config_t scan_conf = {0};
    esp_wifi_set_mode(WIFI_MODE_APSTA);
    esp_wifi_start();
    esp_wifi_scan_start(&scan_conf, true);
    uint16_t ap_count = 0;
    esp_wifi_scan_get_ap_num(&ap_count);
    if (ap_count > 20) ap_count = 20;
    wifi_ap_record_t ap_records[20];
    esp_wifi_scan_get_ap_records(&ap_count, ap_records);
    char *buf = malloc(ap_count * 128 + 32);
    if (!buf) { httpd_resp_send_500(req); return ESP_FAIL; }
    strcpy(buf, "{\"networks\":[");
    for (int i = 0; i < ap_count; i++) {
        char entry[128];
        snprintf(entry, sizeof(entry), "%s{\"ssid\":\"%s\",\"rssi\":%d,\"auth\":%d}",
                 i > 0 ? "," : "", ap_records[i].ssid, ap_records[i].rssi, ap_records[i].authmode);
        strcat(buf, entry);
    }
    strcat(buf, "]}");
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_send(req, buf, strlen(buf));
    free(buf);
    return ESP_OK;
}

static esp_err_t handle_config(httpd_req_t *req)
{
    char buf[512] = {0};
    int ret = httpd_req_recv(req, buf, sizeof(buf) - 1);
    if (ret <= 0) { httpd_resp_send_500(req); return ESP_FAIL; }
    buf[ret] = '\0';
    ln_config_t cfg = {0};
    web_config_load(&cfg);
    char *p = NULL;
    p = strstr(buf, "\"wifi_ssid\"");
    if (p) { p = strchr(p + 11, '"'); if (p) { p++; char *end = strchr(p, '"'); if (end) { int len = end - p; if (len >= LN_MAX_SSID_LEN) len = LN_MAX_SSID_LEN - 1; memcpy(cfg.wifi_ssid, p, len); cfg.wifi_ssid[len] = '\0'; } } }
    p = strstr(buf, "\"wifi_pass\"");
    if (p) { p = strchr(p + 11, '"'); if (p) { p++; char *end = strchr(p, '"'); if (end) { int len = end - p; if (len >= LN_MAX_PASS_LEN) len = LN_MAX_PASS_LEN - 1; memcpy(cfg.wifi_pass, p, len); cfg.wifi_pass[len] = '\0'; } } }
    p = strstr(buf, "\"mqtt_broker\"");
    if (p) { p = strchr(p + 13, '"'); if (p) { p++; char *end = strchr(p, '"'); if (end) { int len = end - p; if (len >= LN_MAX_BROKER_LEN) len = LN_MAX_BROKER_LEN - 1; memcpy(cfg.mqtt_broker, p, len); cfg.mqtt_broker[len] = '\0'; } } }
    p = strstr(buf, "\"mqtt_client\"");
    if (p) { p = strchr(p + 13, '"'); if (p) { p++; char *end = strchr(p, '"'); if (end) { int len = end - p; if (len >= LN_MAX_CLIENT_LEN) len = LN_MAX_CLIENT_LEN - 1; memcpy(cfg.mqtt_client, p, len); cfg.mqtt_client[len] = '\0'; } } }
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

static esp_err_t handle_captive(httpd_req_t *req)
{
    httpd_resp_set_status(req, "302 Found");
    httpd_resp_set_hdr(req, "Location", "http://" AP_IP_ADDR "/");
    httpd_resp_send(req, NULL, 0);
    return ESP_OK;
}

static httpd_handle_t start_webserver(void)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.max_uri_handlers = 8;
    config.stack_size = 8192;
    if (httpd_start(&s_server, &config) == ESP_OK) {
        httpd_uri_t u_root = { .uri = "/", .method = HTTP_GET, .handler = handle_root };
        httpd_uri_t u_status = { .uri = "/api/status", .method = HTTP_GET, .handler = handle_status };
        httpd_uri_t u_scan = { .uri = "/api/scan", .method = HTTP_GET, .handler = handle_scan };
        httpd_uri_t u_config = { .uri = "/api/config", .method = HTTP_POST, .handler = handle_config };
        httpd_uri_t u_restart = { .uri = "/api/restart", .method = HTTP_POST, .handler = handle_restart };
        httpd_uri_t u_cp1 = { .uri = "/generate_204", .method = HTTP_GET, .handler = handle_captive };
        httpd_uri_t u_cp2 = { .uri = "/connecttest.txt", .method = HTTP_GET, .handler = handle_captive };
        httpd_register_uri_handler(s_server, &u_root);
        httpd_register_uri_handler(s_server, &u_status);
        httpd_register_uri_handler(s_server, &u_scan);
        httpd_register_uri_handler(s_server, &u_config);
        httpd_register_uri_handler(s_server, &u_restart);
        httpd_register_uri_handler(s_server, &u_cp1);
        httpd_register_uri_handler(s_server, &u_cp2);
        ESP_LOGI(TAG, "Web server started");
        return s_server;
    }
    return NULL;
}

static void stop_webserver(void)
{
    if (s_server) { httpd_stop(s_server); s_server = NULL; }
}

static void dns_task(void *pvParameters)
{
    char rx_buffer[128];
    struct sockaddr_in source_addr;
    socklen_t socklen = sizeof(source_addr);
    while (1) {
        int len = recvfrom(s_dns_socket, rx_buffer, sizeof(rx_buffer), 0,
                           (struct sockaddr *)&source_addr, &socklen);
        if (len < 0) { vTaskDelay(pdMS_TO_TICKS(100)); continue; }
        if (len < 12) continue;
        uint8_t resp[256];
        memcpy(resp, rx_buffer, len);
        resp[2] = 0x81; resp[3] = 0x80;
        resp[6] = resp[4]; resp[7] = resp[5];
        resp[8] = 0x00; resp[9] = 0x01;
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

static void start_dns_server(void)
{
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(DNS_PORT);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    s_dns_socket = socket(AF_INET, SOCK_DGRAM, 0);
    if (s_dns_socket < 0) return;
    if (bind(s_dns_socket, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(s_dns_socket); s_dns_socket = -1; return;
    }
    xTaskCreate(dns_task, "dns_server", 4096, NULL, 3, &s_dns_task_handle);
    ESP_LOGI(TAG, "DNS server started (captive portal)");
}

static void stop_dns_server(void)
{
    if (s_dns_task_handle) { vTaskDelete(s_dns_task_handle); s_dns_task_handle = NULL; }
    if (s_dns_socket >= 0) { close(s_dns_socket); s_dns_socket = -1; }
}

esp_err_t web_config_start_ap(void)
{
    if (s_ap_active) return ESP_OK;
    ESP_LOGI(TAG, "Starting AP mode for configuration...");
    esp_netif_create_default_wifi_ap();
    uint8_t mac[6];
#if CONFIG_IDF_TARGET_ESP32P4
    esp_wifi_get_mac(WIFI_IF_STA, mac);
#else
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
#endif
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
    start_dns_server();
    start_webserver();
    s_ap_active = true;
    ESP_LOGI(TAG, "AP started: SSID=%s, IP=%s", ap_ssid, AP_IP_ADDR);
    return ESP_OK;
}

esp_err_t web_config_stop_ap(void)
{
    if (!s_ap_active) return ESP_OK;
    stop_webserver();
    stop_dns_server();
    esp_wifi_stop();
    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_start();
    s_ap_active = false;
    return ESP_OK;
}

bool web_config_is_ap_active(void)
{
    return s_ap_active;
}

esp_err_t web_config_load(ln_config_t *cfg)
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(LN_NVS_NAMESPACE, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        memset(cfg, 0, sizeof(ln_config_t));
        return err;
    }
    size_t len;
    int32_t val;
    len = sizeof(cfg->wifi_ssid); nvs_get_str(handle, LN_NVS_KEY_WIFI_SSID, cfg->wifi_ssid, &len);
    len = sizeof(cfg->wifi_pass); nvs_get_str(handle, LN_NVS_KEY_WIFI_PASS, cfg->wifi_pass, &len);
    len = sizeof(cfg->mqtt_broker); nvs_get_str(handle, LN_NVS_KEY_MQTT_BROKER, cfg->mqtt_broker, &len);
    len = sizeof(cfg->mqtt_client); nvs_get_str(handle, LN_NVS_KEY_MQTT_CLIENT, cfg->mqtt_client, &len);
    if (nvs_get_i32(handle, LN_NVS_KEY_BRIGHTNESS, &val) == ESP_OK) cfg->brightness = val; else cfg->brightness = 80;
    if (nvs_get_i32(handle, LN_NVS_KEY_VOLUME, &val) == ESP_OK) cfg->volume = val; else cfg->volume = 50;
    nvs_close(handle);
    return ESP_OK;
}

esp_err_t web_config_save(const ln_config_t *cfg)
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(LN_NVS_NAMESPACE, NVS_READWRITE, &handle);
    if (err != ESP_OK) return err;
    if (cfg->wifi_ssid[0]) nvs_set_str(handle, LN_NVS_KEY_WIFI_SSID, cfg->wifi_ssid);
    if (cfg->wifi_pass[0]) nvs_set_str(handle, LN_NVS_KEY_WIFI_PASS, cfg->wifi_pass);
    if (cfg->mqtt_broker[0]) nvs_set_str(handle, LN_NVS_KEY_MQTT_BROKER, cfg->mqtt_broker);
    if (cfg->mqtt_client[0]) nvs_set_str(handle, LN_NVS_KEY_MQTT_CLIENT, cfg->mqtt_client);
    nvs_set_i32(handle, LN_NVS_KEY_BRIGHTNESS, cfg->brightness);
    nvs_set_i32(handle, LN_NVS_KEY_VOLUME, cfg->volume);
    nvs_commit(handle);
    nvs_close(handle);
    ESP_LOGI(TAG, "Config saved: SSID=%s, Broker=%s", cfg->wifi_ssid, cfg->mqtt_broker);
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
