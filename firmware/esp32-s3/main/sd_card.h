#ifndef SD_CARD_H
#define SD_CARD_H

#include "esp_err.h"
#include <stdbool.h>

typedef struct {
    bool mounted;
    uint64_t total_bytes;
    uint64_t free_bytes;
} sd_card_info_t;

esp_err_t sd_card_init(void);
esp_err_t sd_card_deinit(void);
esp_err_t sd_card_info(sd_card_info_t *info);
bool sd_card_is_mounted(void);

#endif
