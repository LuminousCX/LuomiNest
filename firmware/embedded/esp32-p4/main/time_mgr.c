#include "time_mgr.h"
#include "esp_log.h"
#include "esp_sntp.h"
#include "esp_timer.h"
#include <time.h>
#include <string.h>

static const char *TAG = "time_mgr";

static volatile bool s_synced = false;

static void sntp_sync_cb(struct timeval *tv)
{
    s_synced = true;
    time_t now = tv->tv_sec;
    struct tm tm_info;
    localtime_r(&now, &tm_info);
    char buf[32];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &tm_info);
    ESP_LOGI(TAG, "SNTP synced: %s (CST-8)", buf);
}

esp_err_t time_mgr_init(void)
{
    setenv("TZ", "CST-8", 1);
    tzset();

    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "ntp.aliyun.com");
    esp_sntp_setservername(1, "pool.ntp.org");
    esp_sntp_set_time_sync_notification_cb(sntp_sync_cb);
    esp_sntp_set_sync_mode(SNTP_SYNC_MODE_SMOOTH);
    esp_sntp_init();

    ESP_LOGI(TAG, "SNTP client started (CST-8, servers: ntp.aliyun.com, pool.ntp.org)");
    return ESP_OK;
}

bool time_mgr_is_synced(void)
{
    return s_synced;
}

void time_mgr_get_local_time_str(char *buf, size_t len)
{
    if (!buf || len == 0) return;

    if (!s_synced) {
        snprintf(buf, len, "--:--");
        return;
    }

    struct timeval tv;
    gettimeofday(&tv, NULL);
    time_t now = tv.tv_sec;
    struct tm tm_info;
    localtime_r(&now, &tm_info);
    strftime(buf, len, "%H:%M", &tm_info);
}

void time_mgr_get_date_time_str(char *buf, size_t len)
{
    if (!buf || len == 0) return;

    if (!s_synced) {
        snprintf(buf, len, "----/--/-- --:--:--");
        return;
    }

    struct timeval tv;
    gettimeofday(&tv, NULL);
    time_t now = tv.tv_sec;
    struct tm tm_info;
    localtime_r(&now, &tm_info);
    strftime(buf, len, "%Y/%m/%d %H:%M:%S", &tm_info);
}
