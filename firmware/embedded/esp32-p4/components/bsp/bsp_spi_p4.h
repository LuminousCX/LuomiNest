/**
 * LuomiNest P4 - BSP SPI Master (P4 <-> C6 协处理器)
 * 切片 5a: 物理层初始化 + 收发原语
 *
 * 这一层只负责:
 *   1. 初始化 SPI2 (40 MHz, MODE 0)
 *   2. 提供 bsp_spi_p4_transfer(tx, rx, len) 一问一答
 *   3. 提供 bsp_spi_p4_cs_low/high 片选控制
 *
 * 不负责:
 *   - 9 字节头解析 (这是 drv_spi_master.c 的事)
 *   - CRC16 校验 (drv_spi_master.c 的事)
 *
 * 详细分层见 D:\luominest\firmware\CLAUDE.md §6, §7
 */

#ifndef BSP_SPI_P4_H
#define BSP_SPI_P4_H

#include "esp_err.h"
#include <stdint.h>
#include <stddef.h>

/** 初始化 SPI Master 总线. 多次调用安全 (内部只 init 一次). */
esp_err_t bsp_spi_p4_init(void);

/** 全双工收发. len 字节. tx/rx 任一可为 NULL. */
esp_err_t bsp_spi_p4_transfer(const uint8_t *tx, uint8_t *rx, size_t len);

/** 手动拉低/拉高 CS (绝大多数情况下 transfer 内部自动 CS, 这两个仅供调试). */
esp_err_t bsp_spi_p4_cs_low(void);
esp_err_t bsp_spi_p4_cs_high(void);

#endif /* BSP_SPI_P4_H */
