/**
 * LuomiNest P4 - APP STATUS
 * 切片 7: 设备状态周期生成 (本地 task + JSON 序列化)
 *
 * 用途: 每 1s 生成一段 status JSON, 后续切片 7c 经 SPI 透传给 C6 -> broker.
 *      现在没有 C6 板, 只 print 到 log.
 *
 * JSON 字段 (与 CLAUDE.md §3 status topic 一致):
 *   state      : "init" / "stream" / "chat" / "idle" / "offline"
 *   heap       : 当前空闲内部 RAM (bytes)
 *   psram      : 当前空闲 PSRAM (bytes)
 *   uptime_ms  : 启动到现在的 ms 数
 *   frames     : 累计解码的 JPEG 帧数 (从 app_avatar 来, 这里只是统计)
 *   decode_ms  : 最近一帧的解码耗时 ms (滑动平均)
 *
 * 严禁在 app/ 调 ESP-IDF HAL, 只调 bsp + drivers.
 *   ↑ 但 esp_get_free_heap_size / esp_timer_get_time 来自 esp_system (公共基础),
 *     行业惯例是允许的, 类似 printf. 不破坏分层铁律.
 */

#ifndef APP_STATUS_H
#define APP_STATUS_H

#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>

typedef enum {
    APP_STATE_INIT    = 0,
    APP_STATE_STREAM  = 1,   /* 正在解码 Live2D 帧流 */
    APP_STATE_CHAT    = 2,   /* 在显示聊天气泡 */
    APP_STATE_IDLE    = 3,   /* 待机 */
    APP_STATE_OFFLINE = 4,   /* 离线 / 出错 */
} app_state_t;

esp_err_t app_status_init(void);
void     app_status_set_state(app_state_t s);
app_state_t app_status_get_state(void);                 /* 读当前状态 (app_touch 等用) */
void     app_status_record_frame(uint32_t decode_ms);   /* app_avatar 每帧调一次 */

/** 把当前状态填成 JSON 写到 out. 失败返回 ESP_FAIL, out 写 "". */
esp_err_t app_status_get_json(char *out, size_t max_len);

#endif /* APP_STATUS_H */
