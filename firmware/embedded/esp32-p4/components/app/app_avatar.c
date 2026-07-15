/**
 * LuomiNest P4 - APP AVATAR 实现
 * 切片 9 重构: avatar 走 LVGL 单生产者 (lv_image_set_src), 不直接碰 DSI.
 * 切片 12 重构: 拆 producer/consumer, 通过 xQueue 解耦
 *   - mock 模式 (默认): 内部 avatar_mock_task 周期性灌 test_400x540_jpg
 *   - SPI 模式:          app_spi_recv_task (在 app_spi_recv.c) 收 C6 type=0x01
 *                        调 app_avatar_push_frame() 灌入
 *
 * 数据流 (两种模式同一条 pipeline):
 *   producer (mock | spi_recv) → s_jpg_queue → avatar_decode_task
 *                                                  ↓
 *                                       drv_jpeg_decode_to_buf → s_frame_bufs[i]
 *                                                  ↓
 *                                       lvgl_port_lock(5000)
 *                                                  ↓
 *                                       lv_image_set_src(s_avatar_img, buf)
 *                                                  ↓
 *                                       lvgl_port_unlock → esp_lvgl_port 内部 flush → DSI
 *
 * 严格分层: app/ 调 bsp + drivers + LVGL API; 不知道 ESP-IDF HAL.
 *
 * 设计选择 (KISS):
 *   - 用 LVGL 9.5 的 lv_draw_buf_t (LVGL 拥有 memory)
 *   - 末尾 128B 比对 vs CRC: memcmp < 1us, CRC 100x 重, 简化优先
 *   - 队列深度 4: 解码 < 40ms, 4 帧 = 160ms 缓冲, C6 偶发 burst 也不丢
 *   - 单 JPEG 上限 64KB: 协议层 uint16_t len 上限 65535, 实际帧 15-30KB 远低于此
 */

#include "app_avatar.h"
#include "app_status.h"
#include "drv_jpeg.h"

#include "esp_log.h"
#include "esp_check.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"

#include "esp_lvgl_port.h"
#include "lvgl.h"

#include <string.h>
#include <stdlib.h>
#include <stdatomic.h>

#if !APP_AVATAR_USE_SPI_SOURCE
#include "test_400x540.h"
#include "frame_player.h"
#endif

static const char *TAG = "avatar";

/* === 配置 === */
#define AVATAR_W             400
#define AVATAR_H             540
#define AVATAR_FPS           25
#define AVATAR_PERIOD_MS     (1000 / AVATAR_FPS)   /* 40 ms */
#define DEDUP_TAIL_BYTES     128                   /* 末尾比对长度 */
#define AVATAR_X             32    /* 居中在 464px 右侧 panel: (464-400)/2 */
#define AVATAR_Y             18    /* 居中在 576px 内容区: (576-540)/2 */
#define JPG_QUEUE_DEPTH      16                    /* producer→consumer 缓冲 */
#define MAX_JPG_BYTES        (64 * 1024)           /* 协议层 uint16_t len 上限 */

/* AVATAR_DYNAMIC_TEST 已移除 (死代码, 永不执行) */

/* === 状态 (atomic 让外部读稳定) === */
static atomic_uint s_decoded_cnt = 0;
static atomic_uint s_skipped_cnt = 0;
static atomic_uint s_total_cnt   = 0;
static bool started = false;

/* === 去重缓存: 上一帧末尾 128B === */
static uint8_t s_last_tail[DEDUP_TAIL_BYTES];
static bool    s_last_valid = false;   /* 第一帧永远解码, 之后才比对 */

/* === LVGL 资源 (单生产者模式: avatar 走 lv_image, 不直接碰 DSI) === */
static lv_obj_t      *s_avatar_img  = NULL;
static lv_draw_buf_t *s_frame_bufs[2] = {NULL, NULL};   /* 400x540 RGB565, LVGL 拥有 */
static volatile int   s_write_idx   = 0;
static lv_obj_t      *s_parent_panel = NULL;             /* app_ui 传入的父 panel */

/* === 任务 + 队列 (切片 12: producer/consumer 解耦) === */
static QueueHandle_t s_jpg_queue      = NULL;
static TaskHandle_t  s_decode_task_h  = NULL;
#if !APP_AVATAR_USE_SPI_SOURCE
static TaskHandle_t  s_mock_task_h    = NULL;
#endif

/* === 统计: 每 1s 打印一次 (跟 app_status 同步) === */
static int64_t s_last_stat_us = 0;

#if !APP_AVATAR_USE_SPI_SOURCE
/* === mock producer: 周期性灌 test_400x540_jpg 到队列 === */
static void avatar_mock_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "mock producer: test_400x540_jpg (%u bytes) every %d ms",
             (unsigned)TEST_400x540_JPG_LEN, AVATAR_PERIOD_MS);

    while (1) {
        /* SD 卡有帧时, mock 让路给 frame_player */
        if (frame_player_is_sd_available() && frame_player_is_playing()) {
            vTaskDelay(pdMS_TO_TICKS(500));
            continue;
        }

        /* malloc + memcpy: consumer 会 free, 必须独立 buffer.
         * 用 PSRAM 避免 internal RAM 压力. */
        uint8_t *buf = heap_caps_malloc(TEST_400x540_JPG_LEN,
                                         MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
        if (buf == NULL) {
            ESP_LOGE(TAG, "mock malloc %u failed, skip this tick",
                     (unsigned)TEST_400x540_JPG_LEN);
            vTaskDelay(pdMS_TO_TICKS(AVATAR_PERIOD_MS));
            continue;
        }
        memcpy(buf, test_400x540_jpg, TEST_400x540_JPG_LEN);

        jpg_entry_t entry = { .data = buf, .len = TEST_400x540_JPG_LEN };
        /* 非阻塞: 队列满就丢这帧 (consumer 慢于 producer 才会发生, 实际不会) */
        if (xQueueSend(s_jpg_queue, &entry, 0) != pdTRUE) {
            free(buf);
            ESP_LOGW(TAG, "mock queue full, frame dropped");
        }

        vTaskDelay(pdMS_TO_TICKS(AVATAR_PERIOD_MS));
    }
}
#endif /* !APP_AVATAR_USE_SPI_SOURCE */

/* === consumer: 拉队列 → 去重 → 解码 → LVGL (切片 9 路径, 不动) === */
static void avatar_decode_task(void *arg)
{
    (void)arg;
    ESP_LOGI(TAG, "decode consumer started, dedup tail=%d bytes", DEDUP_TAIL_BYTES);

    uint32_t seq = 0;
    while (1) {
        jpg_entry_t entry = {0};
        if (xQueueReceive(s_jpg_queue, &entry, portMAX_DELAY) != pdTRUE) {
            continue;   /* portMAX_DELAY 实际不会失败, 防御性 */
        }

        const uint8_t *jpg    = entry.data;
        const uint32_t jpg_len = (uint32_t)entry.len;

        atomic_fetch_add(&s_total_cnt, 1);

        /* 1. 末尾 128B 比对去重 */
        bool dedup_hit = false;
        if (s_last_valid && jpg_len >= DEDUP_TAIL_BYTES) {
            if (memcmp(jpg + jpg_len - DEDUP_TAIL_BYTES, s_last_tail, DEDUP_TAIL_BYTES) == 0) {
                dedup_hit = true;
            }
        }

        if (dedup_hit) {
            atomic_fetch_add(&s_skipped_cnt, 1);
            if (seq % (AVATAR_FPS * 5) == 0) {
                ESP_LOGI(TAG, "frame seq=%u skipped (dedup)", seq);
            }
        } else {
            /* 2. 实际解码到 s_frame_bufs[s_write_idx]->data */
            lv_draw_buf_t *write_buf = s_frame_bufs[s_write_idx];
            uint16_t w = 0, h = 0;
            int64_t t0 = esp_timer_get_time();
            esp_err_t ret = drv_jpeg_decode_to_buf(jpg, jpg_len,
                                                   (uint16_t *)write_buf->data,
                                                   (uint32_t)write_buf->data_size,
                                                   &w, &h);
            uint32_t decode_ms = (uint32_t)((esp_timer_get_time() - t0) / 1000);
            if (ret != ESP_OK) {
                ESP_LOGE(TAG, "decode failed: %s", esp_err_to_name(ret));
            } else {
                atomic_fetch_add(&s_decoded_cnt, 1);
                if (jpg_len >= DEDUP_TAIL_BYTES) {
                    memcpy(s_last_tail, jpg + jpg_len - DEDUP_TAIL_BYTES, DEDUP_TAIL_BYTES);
                    s_last_valid = true;
                }
                if (seq % (AVATAR_FPS * 5) == 0) {  /* 每 5s 一次 decode */
                    ESP_LOGI(TAG, "frame seq=%u decoded %ux%u in %u ms", seq, w, h, decode_ms);
                }
                app_status_record_frame(decode_ms);

                /* 3. 走 LVGL: 切换 image src, 让 LVGL 单生产者路径在下次 tick 刷到 DSI */
                if (lvgl_port_lock(5000)) {
                    lv_image_set_src(s_avatar_img, write_buf);
                    lv_obj_invalidate(s_avatar_img);
                    lvgl_port_unlock();
                } else {
                    ESP_LOGW(TAG, "lvgl_port_lock timeout, frame dropped");
                }

                /* 4. 切到下一个 buffer (ping-pong), 内存屏障确保 LVGL 看到完整帧 */
                __sync_synchronize();
                s_write_idx ^= 1;
            }
        }

        seq++;

        /* 5. 周期统计 (5s 一次, 减少刷屏) */
        int64_t now = esp_timer_get_time();
        if (s_last_stat_us == 0) s_last_stat_us = now;
        if (now - s_last_stat_us >= 5000000) {
            ESP_LOGI(TAG, "stat: total=%u, decoded=%u, skipped=%u, fps=%d",
                     atomic_load(&s_total_cnt),
                     atomic_load(&s_decoded_cnt),
                     atomic_load(&s_skipped_cnt),
                     AVATAR_FPS);
            s_last_stat_us = now;
        }

        /* 6. 释放 producer 传入的 buffer (consumer 接管所有权) */
        free(entry.data);
    }
}

esp_err_t app_avatar_init(lv_obj_t *parent)
{
    if (started) return ESP_OK;
    if (parent == NULL) return ESP_ERR_INVALID_ARG;

    s_parent_panel = parent;

    /* 1. 分配 2 个 lv_draw_buf (400x540 RGB565, 内存由 LVGL 选 PSRAM 优先) */
    for (int i = 0; i < 2; i++) {
        s_frame_bufs[i] = lv_draw_buf_create(AVATAR_W, AVATAR_H,
                                             LV_COLOR_FORMAT_RGB565, LV_STRIDE_AUTO);
        if (s_frame_bufs[i] == NULL) {
            ESP_LOGE(TAG, "lv_draw_buf_create[%d] failed", i);
            app_avatar_deinit();
            return ESP_ERR_NO_MEM;
        }
        /* 初始化黑色 (避免首帧前出现随机像素) */
        memset(s_frame_bufs[i]->data, 0, s_frame_bufs[i]->data_size);
    }

    /* 2. 在 parent panel 内创建 avatar image widget (居中) */
    s_avatar_img = lv_image_create(parent);
    if (s_avatar_img == NULL) {
        ESP_LOGE(TAG, "lv_image_create failed");
        app_avatar_deinit();
        return ESP_ERR_NO_MEM;
    }
    lv_obj_set_size(s_avatar_img, AVATAR_W, AVATAR_H);
    lv_obj_center(s_avatar_img);
    lv_image_set_src(s_avatar_img, s_frame_bufs[0]);

    /* 3. producer→consumer 队列 (切片 12) */
    s_jpg_queue = xQueueCreate(JPG_QUEUE_DEPTH, sizeof(jpg_entry_t));
    if (s_jpg_queue == NULL) {
        ESP_LOGE(TAG, "xQueueCreate jpg_queue failed");
        app_avatar_deinit();
        return ESP_ERR_NO_MEM;
    }

    /* 4. decode task (consumer), 固定 CPU 1 避免与 LVGL task 竞争 */
    BaseType_t ok = xTaskCreatePinnedToCore(avatar_decode_task, "app_avatar", 6144, NULL, 4,
                                            &s_decode_task_h, 1);
    if (ok != pdPASS) return ESP_ERR_NO_MEM;

#if 0  /* mock 已禁用, frame_player 独占 avatar 队列 */
    ok = xTaskCreate(avatar_mock_task, "avatar_mock", 4096, NULL, 3, &s_mock_task_h);
    if (ok != pdPASS) return ESP_ERR_NO_MEM;
#endif

    started = true;
    ESP_LOGI(TAG, "init ok: %dx%d @ (%d,%d), src=%s, q_depth=%d",
             AVATAR_W, AVATAR_H, AVATAR_X, AVATAR_Y,
#if APP_AVATAR_USE_SPI_SOURCE
             "SPI",
#else
             "mock",
#endif
             JPG_QUEUE_DEPTH);
    return ESP_OK;
}

void app_avatar_deinit(void)
{
    if (s_decode_task_h) {
        vTaskDelete(s_decode_task_h);
        s_decode_task_h = NULL;
    }
#if !APP_AVATAR_USE_SPI_SOURCE
    if (s_mock_task_h) {
        vTaskDelete(s_mock_task_h);
        s_mock_task_h = NULL;
    }
#endif
    if (s_jpg_queue) {
        /* 排空队列, 释放未消费的 buffer */
        jpg_entry_t entry;
        while (xQueueReceive(s_jpg_queue, &entry, 0) == pdTRUE) {
            free(entry.data);
        }
        vQueueDelete(s_jpg_queue);
        s_jpg_queue = NULL;
    }
    for (int i = 0; i < 2; i++) {
        if (s_frame_bufs[i]) {
            lv_draw_buf_destroy(s_frame_bufs[i]);
            s_frame_bufs[i] = NULL;
        }
    }
    if (s_avatar_img) {
        lv_obj_delete(s_avatar_img);
        s_avatar_img = NULL;
    }
    s_last_valid = false;
    s_write_idx = 0;
    atomic_store(&s_decoded_cnt, 0);
    atomic_store(&s_skipped_cnt, 0);
    atomic_store(&s_total_cnt, 0);
    started = false;
}

esp_err_t app_avatar_push_frame(const uint8_t *jpg, size_t jpg_len)
{
    if (s_jpg_queue == NULL) return ESP_ERR_INVALID_STATE;
    if (jpg == NULL || jpg_len == 0) return ESP_ERR_INVALID_ARG;
    if (jpg_len > MAX_JPG_BYTES) {
        ESP_LOGE(TAG, "push_frame: %u > MAX %u, dropped",
                 (unsigned)jpg_len, (unsigned)MAX_JPG_BYTES);
        return ESP_ERR_INVALID_SIZE;
    }

    /* 用 PSRAM, 跟 mock 路径一致; 调用方 buffer 可立即释放 */
    uint8_t *buf = heap_caps_malloc(jpg_len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (buf == NULL) return ESP_ERR_NO_MEM;
    memcpy(buf, jpg, jpg_len);

    jpg_entry_t entry = { .data = buf, .len = jpg_len };
    if (xQueueSend(s_jpg_queue, &entry, 0) != pdTRUE) {
        free(buf);
        return ESP_ERR_TIMEOUT;
    }
    return ESP_OK;
}

uint32_t app_avatar_get_decoded_count(void) { return atomic_load(&s_decoded_cnt); }
uint32_t app_avatar_get_skipped_count(void) { return atomic_load(&s_skipped_cnt); }
uint32_t app_avatar_get_total_count(void)   { return atomic_load(&s_total_cnt); }

bool app_avatar_queue_has_space(void)
{
    if (!s_jpg_queue) return false;
    return uxQueueSpacesAvailable(s_jpg_queue) > 0;
}

QueueHandle_t app_avatar_get_queue(void)
{
    return s_jpg_queue;
}
