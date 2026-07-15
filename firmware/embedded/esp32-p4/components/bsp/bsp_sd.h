/**
 * LuomiNest P4 - BSP SD 卡 (SDMMC 4-bit)
 * 从旧 esp32-p4/main/main.c init_sdcard() 移植, 改为独立 BSP 组件
 */

#ifndef BSP_SD_H
#define BSP_SD_H

#include "esp_err.h"
#include <stdbool.h>

/** 挂载 SD 卡到 /sdcard, 自动尝试 4-bit/1-bit + 多频率 */
esp_err_t bsp_sd_mount(void);

/** 卸载 SD 卡 */
esp_err_t bsp_sd_unmount(void);

/** SD 卡是否已挂载 */
bool bsp_sd_is_mounted(void);

#endif /* BSP_SD_H */
