#ifndef AVATAR_ENGINE_H
#define AVATAR_ENGINE_H

#include "lvgl.h"
#include "lcd_parallel.h"
#include "frame_player.h"
#include <stdint.h>
#include <stdbool.h>

typedef enum {
    AVATAR_STATE_IDLE = 0,
    AVATAR_STATE_HAPPY,
    AVATAR_STATE_SAD,
    AVATAR_STATE_ANGRY,
    AVATAR_STATE_SURPRISED,
    AVATAR_STATE_WAVE,
    AVATAR_STATE_NOD,
    AVATAR_STATE_THINK,
    AVATAR_STATE_SLEEP,
    AVATAR_STATE_TALK,
    AVATAR_STATE_CUSTOM,
    AVATAR_STATE_MAX
} avatar_state_t;

typedef struct {
    uint32_t frames_displayed;
    uint32_t decode_errors;
    uint32_t local_frames_played;
    uint32_t last_frame_ms;
} avatar_stats_t;

typedef void (*avatar_state_changed_cb_t)(avatar_state_t new_state);

esp_err_t avatar_engine_init(lv_obj_t *parent, lcd_parallel_handle_t *lcd);
esp_err_t avatar_engine_play_state(avatar_state_t state);
esp_err_t avatar_engine_stop(void);
avatar_state_t avatar_engine_get_state(void);
esp_err_t avatar_engine_register_state_cb(avatar_state_changed_cb_t cb);
void avatar_engine_on_frame(const uint8_t *data, uint32_t len, frame_format_t format);
const avatar_stats_t *avatar_engine_get_stats(void);
void avatar_engine_reset_stats(void);
const char *avatar_engine_state_name(avatar_state_t state);

#endif
