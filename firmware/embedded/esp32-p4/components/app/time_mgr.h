/**
 * LuomiNest P4 - SNTP 时间管理
 * 从旧 esp32-p4/main/time_mgr.c 移植, 代码不变
 */

#ifndef TIME_MGR_H
#define TIME_MGR_H

#include "esp_err.h"
#include <stdbool.h>

/** 启动 SNTP 客户端 (CST-8 时区, ntp.aliyun.com + pool.ntp.org) */
esp_err_t time_mgr_init(void);

/** NTP 是否已同步 */
bool time_mgr_is_synced(void);

/** 获取本地时间字符串 "HH:MM" */
void time_mgr_get_local_time_str(char *buf, size_t len);

/** 获取本地日期时间字符串 "YYYY/MM/DD HH:MM:SS" */
void time_mgr_get_date_time_str(char *buf, size_t len);

#endif /* TIME_MGR_H */
