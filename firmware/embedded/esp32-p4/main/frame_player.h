#ifndef FRAME_PLAYER_H
#define FRAME_PLAYER_H

#include "esp_err.h"
#include "avatar_engine.h"
#include <stdbool.h>
#include <stdint.h>

#define FP_MAX_STATE_NAME  32
#define FP_MAX_PATH        256
#define FP_DEFAULT_FPS     30
#define FP_MANIFEST_FILE   "/sdcard/frames/manifest.json"

typedef enum {
    FP_FMT_AUTO = 0,
    FP_FMT_JPEG,
    FP_FMT_RAW,
} fp_format_t;

typedef enum {
    FP_MODE_IDLE = 0,
    FP_MODE_PLAYING,
    FP_MODE_PAUSED,
} fp_playback_mode_t;

typedef struct {
    char name[FP_MAX_STATE_NAME];
    char path[FP_MAX_PATH];
    uint16_t frame_count;
    uint16_t fps;
    bool loop;
    fp_format_t format;
} fp_sequence_t;

typedef struct {
    fp_sequence_t sequences[AVATAR_STATE_MAX];
    int sequence_count;
    bool sd_available;
    fp_playback_mode_t mode;
} fp_context_t;

typedef void (*fp_frame_ready_cb_t)(const uint8_t *frame_data, uint32_t frame_len);

esp_err_t frame_player_init(void);
esp_err_t frame_player_start(avatar_state_t state);
esp_err_t frame_player_stop(void);
esp_err_t frame_player_pause(void);
esp_err_t frame_player_resume(void);
esp_err_t frame_player_set_state(avatar_state_t state);
bool frame_player_is_playing(void);
bool frame_player_has_state(avatar_state_t state);
bool frame_player_is_sd_available(void);
void frame_player_register_frame_cb(fp_frame_ready_cb_t cb);
void frame_player_task(void *pvParameter);

#endif
