#ifndef TIME_MGR_H
#define TIME_MGR_H

#include "esp_err.h"
#include <stdbool.h>

esp_err_t time_mgr_init(void);
bool time_mgr_is_synced(void);
void time_mgr_get_local_time_str(char *buf, size_t len);
void time_mgr_get_date_time_str(char *buf, size_t len);

#endif
