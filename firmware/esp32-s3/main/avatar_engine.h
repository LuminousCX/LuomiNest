#ifndef AVATAR_ENGINE_H
#define AVATAR_ENGINE_H

#include "lvgl.h"
#include "esp_err.h"

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
    AVATAR_STATE_STREAMING,
    AVATAR_STATE_MAX
} avatar_state_t;

typedef struct {
    char name[32];
    uint16_t frame_count;
    uint16_t fps;
    bool loop;
} avatar_action_t;

typedef struct {
    uint32_t frames_received;
    uint32_t frames_displayed;
    uint32_t frames_skipped_dedup;
    uint32_t frames_skipped_error;
    uint32_t decode_errors;
    uint32_t last_decode_ms;
} avatar_stats_t;

typedef void (*avatar_state_changed_cb_t)(avatar_state_t new_state);

esp_err_t avatar_engine_init(lv_obj_t *parent);
esp_err_t avatar_engine_play_state(avatar_state_t state);
esp_err_t avatar_engine_play_action(const char *action_name, uint16_t frame_count, uint16_t fps, bool loop);
esp_err_t avatar_engine_stop(void);
avatar_state_t avatar_engine_get_state(void);
esp_err_t avatar_engine_register_state_cb(avatar_state_changed_cb_t cb);
esp_err_t avatar_engine_show_frame(const uint8_t *frame_data, uint32_t frame_len);
esp_err_t avatar_engine_set_mouth_openness(uint8_t percent);
const avatar_stats_t *avatar_engine_get_stats(void);
void avatar_engine_reset_stats(void);

#endif
