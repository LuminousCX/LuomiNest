/**
 * LuomiNest P4 - BSP Ethernet (IP101G RMII)
 * 从旧 esp32-p4/main/eth_mgr.c 移植, 改为独立 BSP 组件
 */

#ifndef BSP_ETH_H
#define BSP_ETH_H

#include "esp_err.h"
#include <stdbool.h>

typedef void (*bsp_eth_connected_cb_t)(void);
typedef void (*bsp_eth_disconnected_cb_t)(void);

/** 初始化以太网 (EMAC + RMII + IP101G PHY) */
esp_err_t bsp_eth_init(void);

/** 启动以太网 */
esp_err_t bsp_eth_start(void);

/** 停止以太网 */
esp_err_t bsp_eth_stop(void);

/** 是否已连接 */
bool bsp_eth_is_connected(void);

/** 获取 IP 字符串 */
void bsp_eth_get_ip_str(char *buf, size_t buf_len);

/** 注册回调 */
esp_err_t bsp_eth_register_connected_cb(bsp_eth_connected_cb_t cb);
esp_err_t bsp_eth_register_disconnected_cb(bsp_eth_disconnected_cb_t cb);

#endif /* BSP_ETH_H */
