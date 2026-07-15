/**
 * LuomiNest P4 - APP SPI RECV
 * 切片 12: P4 SPI Master 接收 task, 收 C6 经 broker 透传过来的数据
 *
 * 路由 (按 drv_spi_master.h 的 4 种 type):
 *   TYPE_JPEG (0x01) → app_avatar_push_frame(payload, len)
 *   TYPE_CHAT (0x02) → app_chat_push_message(CHAT_ROLE_AI, text)  (协议不带 role, 默认 AI)
 *   TYPE_CMD  (0x03) → log 关键字 (8B ASCII: happy/sad/...), 后续接情绪/动作
 *   其它             → log warn, ignore
 *
 * 启用条件: APP_AVATAR_USE_SPI_SOURCE=1 (在 app_avatar.h)
 *   = 0 (默认) 时 init() 是 no-op, 不浪费 CPU 在 timeout 轮询上.
 *
 * 严禁在 app/ 调 ESP-IDF HAL, 只调 bsp + drivers.
 */

#ifndef APP_SPI_RECV_H
#define APP_SPI_RECV_H

#include "esp_err.h"

esp_err_t app_spi_recv_init(void);
void      app_spi_recv_deinit(void);

#endif /* APP_SPI_RECV_H */
