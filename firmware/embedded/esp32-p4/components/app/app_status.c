/**
 * LuomiNest P4 - APP STATUS 实现
 * 切片 7: 1s 周期 task + JSON 序列化 + 帧统计
 * 切片 12: 加 drv_spi_send_frame(0x10, ...) 把 JSON 推给 C6 透传到 broker
 *
 * 这一层不知道 SPI 协议, 只生成 JSON 字符串; 推送用 drv_spi_master API.
 *
 * 设计选择 (KISS):
 *   - 同时打 UART log + SPI send: dev 时看 log, 生产时看 broker, 不互斥
 *   - SPI send 失败不重试, 只 warn: status 1s/条, 下一条马上来
 *   - seq 单调递增 (atomic), 给 broker 端可选用作乱序检测
 *   - 走 bsp_spi_p4_transfer 内部 mutex: 跟 spi_recv 任务自动互斥
 */

#include "app_status.h"
#include "drv_spi_master.h"

#include "esp_log.h"
#include "esp_check.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdio.h>
#include <string.h>
#include <stdatomic.h>

static const char *TAG = "app_status";

/* === 全局状态 (atomic 让 task / 业务回调都安全) === */
static atomic_int       s_state     = APP_STATE_INIT;
static atomic_uint      s_frame_cnt = 0;          /* 累计帧数 */
static atomic_uint      s_decode_ms_avg = 0;      /* 滑动平均 (近似) */
static atomic_uint      s_tx_seq    = 0;          /* SPI 发送帧序号, 单调递增 */

/* === 滑动平均: alpha=0.2 (新值权重) === */
#define DECODE_MS_EMA_ALPHA  20   /* 分子 */
#define DECODE_MS_EMA_DENOM  100

static void status_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "task started, period 1s, also SPI-pushing status (type=0x10)");

    while (1) {
        char json[256] = {0};
        if (app_status_get_json(json, sizeof(json)) == ESP_OK) {
            ESP_LOGI(TAG, "%s", json);

            /* 切片 12: 推给 C6, C6 收到后透传到 broker luominest/p4/status */
            uint16_t seq = (uint16_t)atomic_fetch_add(&s_tx_seq, 1);
            esp_err_t sr = drv_spi_send_frame(DRV_SPI_TYPE_STATUS,
                                              (const uint8_t *)json,
                                              (uint16_t)strlen(json),
                                              seq);
            if (sr != ESP_OK) {
                /* 通常无 C6 时 SPI 物理上无应答, 但 bsp 层 polling_transmit 不会失败.
                 * 失败一般是 ESP_ERR_INVALID_STATE (bsp_spi 未 init), 这里 warn 一次. */
                static bool warned = false;
                if (!warned) {
                    ESP_LOGW(TAG, "spi send status failed: %s (suppressing further)",
                             esp_err_to_name(sr));
                    warned = true;
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

esp_err_t app_status_init(void)
{
    /* task 创建一次. priority=2 较低, 不抢占 LCD/JPEG task.
     * 栈 4096: ESP-IDF 5.x snprintf + ESP_LOGI 走 vfprintf 全栈, 2048 不够会 stack protection fault. */
    static bool started = false;
    if (started) return ESP_OK;
    BaseType_t ok = xTaskCreate(status_task, "app_status", 4096, NULL, 2, NULL);
    if (ok != pdPASS) return ESP_ERR_NO_MEM;
    started = true;
    return ESP_OK;
}

void app_status_set_state(app_state_t s)
{
    atomic_store(&s_state, s);
}

app_state_t app_status_get_state(void)
{
    return (app_state_t)atomic_load(&s_state);
}

void app_status_record_frame(uint32_t decode_ms)
{
    atomic_fetch_add(&s_frame_cnt, 1);

    /* EMA: new = old * (1-a) + ms * a
     * 我们用整数, 分子分母都放大 100 */
    uint32_t old_avg = atomic_load(&s_decode_ms_avg);
    uint32_t new_avg = (old_avg * (DECODE_MS_EMA_DENOM - DECODE_MS_EMA_ALPHA)
                       + decode_ms * DECODE_MS_EMA_ALPHA) / DECODE_MS_EMA_DENOM;
    atomic_store(&s_decode_ms_avg, new_avg);
}

esp_err_t app_status_get_json(char *out, size_t max_len)
{
    if (out == NULL || max_len == 0) return ESP_ERR_INVALID_ARG;

    const char *state_str = "?";
    switch (atomic_load(&s_state)) {
        case APP_STATE_INIT:    state_str = "init";    break;
        case APP_STATE_STREAM:  state_str = "stream";  break;
        case APP_STATE_CHAT:    state_str = "chat";    break;
        case APP_STATE_IDLE:    state_str = "idle";    break;
        case APP_STATE_OFFLINE: state_str = "offline"; break;
    }

    uint32_t heap    = esp_get_free_heap_size();
    uint32_t psram   = (uint32_t)heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    uint64_t uptime  = esp_timer_get_time() / 1000;  /* ms */
    uint32_t frames  = atomic_load(&s_frame_cnt);
    uint32_t dec_ms  = atomic_load(&s_decode_ms_avg);

    int n = snprintf(out, max_len,
        "{\"state\":\"%s\",\"heap\":%u,\"psram\":%u,\"uptime_ms\":%llu,"
        "\"frames\":%u,\"decode_ms\":%u}",
        state_str, (unsigned)heap, (unsigned)psram,
        (unsigned long long)uptime, (unsigned)frames, (unsigned)dec_ms);
    if (n < 0 || (size_t)n >= max_len) {
        out[0] = '\0';
        return ESP_FAIL;
    }
    return ESP_OK;
}
