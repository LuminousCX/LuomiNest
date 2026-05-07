#ifndef FRAME_PLAYER_H
#define FRAME_PLAYER_H

#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>

typedef void (*frame_player_frame_cb_t)(const uint8_t *jpeg_data, uint32_t jpeg_len);
typedef void (*frame_player_done_cb_t)(const char *sequence_name);

esp_err_t frame_player_init(void);
esp_err_t frame_player_start(const char *sequence_name, uint16_t fps, bool loop);
esp_err_t frame_player_stop(void);
bool frame_player_is_playing(void);
void frame_player_register_frame_cb(frame_player_frame_cb_t cb);
void frame_player_register_done_cb(frame_player_done_cb_t cb);

#endif
