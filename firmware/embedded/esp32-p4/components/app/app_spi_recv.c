/**
 * LuomiNest P4 - APP SPI RECV 实现
 * 切片 12: 阻塞轮询 drv_spi_recv_frame, 按 type 路由到 app_avatar / app_chat
 *
 * 设计选择 (KISS):
 *   - 单 task 串行收 + 路由, 不做复杂多 task 调度. C6 1 msg/4s + 25 FPS JPEG,
 *     spi 速率 40MHz, 收一帧 30KB ~7.5ms, 完全来得及
 *   - payload buffer 64KB: 协议层 uint16_t len 上限 65535, 实际 JPEG ~15-30KB
 *   - timeout 50ms: 让出 CPU 给其他 task, 不 busy loop
 *   - chat 文本用 malloc 复制: 调用 app_chat_push_message 后 payload 立刻被复用
 *   - 收 100 帧 / 错 100 次 各打一条统计, 减少 log 刷屏
 */

#include "app_spi_recv.h"
#include "app_avatar.h"
#include "app_chat.h"
#include "drv_spi_master.h"

#include "esp_log.h"
#include "esp_check.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include <stdlib.h>
#include <string.h>

static const char *TAG = "spi_recv";

#define RECV_PAYLOAD_CAP   (64 * 1024)  /* 协议 uint16_t len 上限 65535 */
#define RECV_TIMEOUT_MS    50           /* 阻塞收, 50ms 让出 CPU */
#define RECV_TASK_PRIO     3            /* < decode(4) / lvgl(4), > status(2) */
#define RECV_TASK_STACK    4096

static TaskHandle_t s_recv_task_h = NULL;
static volatile bool s_running = false;

static void spi_recv_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "started, polling SPI (timeout %d ms), payload cap=%u",
             RECV_TIMEOUT_MS, (unsigned)RECV_PAYLOAD_CAP);

    /* payload 一次性 malloc, 复用 */
    uint8_t *payload = malloc(RECV_PAYLOAD_CAP);
    if (payload == NULL) {
        ESP_LOGE(TAG, "payload malloc %u failed, task exit",
                 (unsigned)RECV_PAYLOAD_CAP);
        s_recv_task_h = NULL;
        vTaskDelete(NULL);  /* 永不返回 */
    }

    uint32_t recv_cnt = 0, err_cnt = 0;

    while (s_running) {
        uint8_t  type = 0;
        uint16_t len  = 0;
        esp_err_t ret = drv_spi_recv_frame(&type, payload, RECV_PAYLOAD_CAP,
                                           &len, RECV_TIMEOUT_MS);
        if (ret == ESP_ERR_TIMEOUT) {
            continue;   /* 正常空闲, 不刷 log */
        }
        if (ret != ESP_OK) {
            err_cnt++;
            /* drv_spi_recv_frame 内部已 log 详细原因, 这里只统计 */
            if (err_cnt % 100 == 1) {
                ESP_LOGW(TAG, "recv errors so far: %u (last: %s)",
                         err_cnt, esp_err_to_name(ret));
            }
            vTaskDelay(pdMS_TO_TICKS(10));
            continue;
        }

        recv_cnt++;
        if (recv_cnt == 1 || recv_cnt % 100 == 0) {
            ESP_LOGI(TAG, "recv #%u: type=0x%02X len=%u", recv_cnt, type, len);
        }

        switch (type) {
        case DRV_SPI_TYPE_JPEG:
            /* JPEG 字节流 → avatar pipeline. push_frame 内部 malloc + memcpy. */
            app_avatar_push_frame(payload, len);
            break;

        case DRV_SPI_TYPE_CHAT: {
            /* payload 不是以 '\0' 结尾的, 末尾加 NUL 后传给 chat.
             * 用小 malloc 避免污染 64KB 栈. */
            if (len >= RECV_PAYLOAD_CAP) len = (uint16_t)(RECV_PAYLOAD_CAP - 1);
            char *text = malloc((size_t)len + 1);
            if (text == NULL) {
                ESP_LOGE(TAG, "chat text malloc %u failed", (unsigned)len + 1);
                break;
            }
            memcpy(text, payload, len);
            text[len] = '\0';
            /* 协议层不带 role 字节, 暂时都按 AI 渲染 (左侧灰底) */
            esp_err_t cr = app_chat_push_message(CHAT_ROLE_AI, text);
            if (cr != ESP_OK) {
                ESP_LOGW(TAG, "chat push failed: %s", esp_err_to_name(cr));
            }
            free(text);
            break;
        }

        case DRV_SPI_TYPE_CMD:
            /* CLAUDE.md §6: 8B ASCII 关键字, happy/sad/talk_start/...
             * 当前 app 没有 emotion/animation 路径, 只 log. */
            ESP_LOGI(TAG, "cmd: '%.*s' (8B keyword, no handler yet)",
                     len > 8 ? 8 : len, (const char *)payload);
            break;

        default:
            ESP_LOGW(TAG, "unknown type 0x%02X, len=%u, ignored", type, len);
            break;
        }
    }

    free(payload);
    s_recv_task_h = NULL;
    vTaskDelete(NULL);
}

esp_err_t app_spi_recv_init(void)
{
`#if` APP_AVATAR_USE_SPI_SOURCE
    if (s_recv_task_h) return ESP_OK;
    s_running = true;
    BaseType_t ok = xTaskCreate(spi_recv_task, "spi_recv", RECV_TASK_STACK,
                                NULL, RECV_TASK_PRIO, &s_recv_task_h);
    if (ok != pdPASS) {
        s_running = false;
        return ESP_ERR_NO_MEM;
    }
    ESP_LOGI(TAG, "init ok (SPI source mode)");
    return ESP_OK;
`#else`
    /* mock 模式下不启动 task, 避免空转 50ms 轮询浪费 CPU.
     * 用户切换到 SPI 模式时, 改 app_avatar.h 的宏 + clean build 即可. */
    ESP_LOGW(TAG, "skip init (APP_AVATAR_USE_SPI_SOURCE=0, mock source active)");
    return ESP_OK;
`#endif`
}

void app_spi_recv_deinit(void)
{
    s_running = false;
    while (s_recv_task_h != NULL) {
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
