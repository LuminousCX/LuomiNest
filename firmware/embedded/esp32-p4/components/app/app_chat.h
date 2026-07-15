/**
 * LuomiNest P4 - APP CHAT (LVGL 9 气泡)
 * 切片 9: 队列 + 滚动 + FIFO 上限 64 + mock 定时器
 *
 * 数据流 (mock 模式, 后续接 SPI 真实源在切片 5c+6):
 *   esp_timer (4s) → push_chat_msg_queue → chat_task → LVGL widget → DPI fb
 *
 * 公共 API:
 *   app_chat_init()           - 启 LVGL + chat task + mock timer (一次性)
 *   app_chat_deinit()         - 停 mock timer + delete tasks (YAGNI, 留 OTA 时用)
 *   app_chat_push_message()   - 推一条气泡 (后续 SPI 接收 type=0x02 时调)
 *   app_chat_get_count()      - 当前气泡数 (测试用)
 *
 * 设计选择 (KISS):
 *   - LVGL 9 左侧 560px 面板, 由 app_ui 传入 parent
 *   - LVGL API 全在 chat_task 单点执行 (LVGL 不是线程安全)
 *   - mock 用 esp_timer 触发, xQueueSend 进 chat_task, 不在 ISR 直接调 LVGL
 *   - FIFO 64 上限, 超出删最旧, 不存历史
 *   - 字体用内置 Montserrat 16 (英文 OK, 中文会显 □, 后续切片换 CJK font)
 */

#ifndef APP_CHAT_H
#define APP_CHAT_H

#include "lvgl.h"
#include "esp_err.h"
#include <stdint.h>

typedef enum {
    CHAT_ROLE_USER,    /* 右对齐, 蓝底白字 */
    CHAT_ROLE_AI,      /* 左对齐, 灰底深字 */
} chat_role_t;

/** 启 chat task + mock timer. parent 由 app_ui 传入 (左侧 panel). */
esp_err_t app_chat_init(lv_obj_t *parent);

/** 停 mock timer + delete task. 留 OTA 切换. */
void app_chat_deinit(void);

/** 推一条气泡. 后续 SPI recv task 收 type=0x02 调这个.
 *  @param role  CHAT_ROLE_USER / CHAT_ROLE_AI
 *  @param text  UTF-8 字符串, 不带 BOM. 会复制内部存储, 调用方 buffer 可立即释放. */
esp_err_t app_chat_push_message(chat_role_t role, const char *text);

/** 当前气泡数 (测试/调试用). */
uint32_t app_chat_get_count(void);

#endif /* APP_CHAT_H */
