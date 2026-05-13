#ifndef ETH_MGR_H
#define ETH_MGR_H

#include "esp_err.h"
#include <stdbool.h>

typedef void (*eth_connected_cb_t)(void);
typedef void (*eth_disconnected_cb_t)(void);

esp_err_t eth_mgr_init(void);
esp_err_t eth_mgr_start(void);
esp_err_t eth_mgr_stop(void);
bool eth_mgr_is_connected(void);
void eth_mgr_get_ip_str(char *buf, size_t buf_len);
esp_err_t eth_mgr_register_connected_cb(eth_connected_cb_t cb);
esp_err_t eth_mgr_register_disconnected_cb(eth_disconnected_cb_t cb);

#endif
