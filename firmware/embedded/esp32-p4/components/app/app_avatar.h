/**
 * LuomiNest P4 - APP AVATAR
 * 切片 8: 整帧去重 (末尾 128B 比对) + JPEG 解码 + LCD 显示
 * 切片 12: 拆成 producer/consumer + FreeRTOS queue
 *   - mock 模式 (默认): app_avatar 内部 avatar_mock_task 周期性灌 test_400x540_jpg
 *   - SPI 模式:        app_spi_recv_task (在 app_spi_recv.c) 收 C6 type=0x01
 *                       调 app_avatar_push_frame() 灌入
 *
 * 数据流 (两种模式同一条 pipeline):
 *   producer (mock | spi_recv) → xQueue s_jpg_queue → decode_task → drv_jpeg → LVGL
 *
 * 设计选择 (KISS):
 *   - 末尾 128B 比对 vs CRC: memcmp < 1us, CRC 算法 100x 重, 简化优先
 *   - 队列深度 4: 解码 < 40ms, 4 帧 = 160ms 缓冲, C6 偶发 burst 也不丢
 *   - 单 JPEG 上限 64KB: 协议层 uint16_t len 上限 65535, 实际帧 15-30KB 远低于此
 *
 * 严禁在 app/ 调 ESP-IDF HAL, 只调 bsp + drivers.
 */

#ifndef APP_AVATAR_H
#define APP_AVATAR_H

#include "lvgl.h"
#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>

/* 切片 12: 数据源开关 (构建时常量, 切换后需 idf.py clean)
 *   0 = mock 模式: avatar_mock_task 周期性灌 test_400x540_jpg (默认, 无 C6 调试)
 *   1 = SPI 模式:  app_spi_recv_task (在 app_spi_recv.c) 是唯一 producer */
#define APP_AVATAR_USE_SPI_SOURCE  0

/** 启动 avatar (建队列 + decode task + 条件 mock task). parent 由 app_ui 传入 (右侧 panel). */
esp_err_t app_avatar_init(lv_obj_t *parent);

/** 停 decode task + mock task. 留 OTA 切换. */
void app_avatar_deinit(void);

/** SPI 源: 推一帧 JPEG 给 decode pipeline.
 *  内部 malloc + memcpy, 调用方 buffer 可立即释放. JPEG 字节流所有权转移.
 *  @return ESP_OK / ESP_ERR_INVALID_STATE (未 init) / ESP_ERR_INVALID_ARG / ESP_ERR_NO_MEM
 *          / ESP_ERR_TIMEOUT (queue 满) */
esp_err_t app_avatar_push_frame(const uint8_t *jpg, size_t jpg_len);

uint32_t app_avatar_get_decoded_count(void);   /* 实际解码次数 */
uint32_t app_avatar_get_skipped_count(void);   /* 末尾 128B 命中跳过次数 */
uint32_t app_avatar_get_total_count(void);     /* 收帧总数 */
bool app_avatar_queue_has_space(void);          /* 队列是否有空位 */

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

/* 队列条目 (frame_player 零拷贝用) */
typedef struct {
    uint8_t *data;
    size_t   len;
} jpg_entry_t;

QueueHandle_t app_avatar_get_queue(void);       /* 获取内部队列 (零拷贝推帧用) */

#endif /* APP_AVATAR_H */
