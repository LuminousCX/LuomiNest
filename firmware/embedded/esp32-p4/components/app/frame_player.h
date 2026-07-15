/**
 * LuomiNest P4 - SD 卡帧序列播放器
 * 从旧 esp32-p4/main/frame_player.c 移植, 适配新架构:
 *   - 不再依赖 avatar_engine.h, 自定义 avatar_state_t
 *   - 帧回调改为 app_avatar_push_frame() (producer 模式)
 *   - 用 cJSON 解析 manifest.json
 */

#ifndef FRAME_PLAYER_H
#define FRAME_PLAYER_H

#include "esp_err.h"
#include <stdbool.h>
#include <stdint.h>

#define FP_MAX_STATE_NAME  32
#define FP_MAX_PATH        256
#define FP_DEFAULT_FPS     15    /* 尽量快, 实际由解码速度限制 */
#define FP_MANIFEST_FILE   "/sdcard/frames/manifest.json"

/* Avatar 表情状态 (从旧 avatar_engine.h 移植) */
typedef enum {
    AVATAR_STATE_IDLE = 0,
    AVATAR_STATE_HAPPY,
    AVATAR_STATE_SAD,
    AVATAR_STATE_ANGRY,
    AVATAR_STATE_SURPRISED,
    AVATAR_STATE_THINK,
    AVATAR_STATE_NEUTRAL,
    AVATAR_STATE_TALK,
    AVATAR_STATE_CUSTOM,
    AVATAR_STATE_STREAMING,
    AVATAR_STATE_MAX
} avatar_state_t;

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

/** 初始化帧播放器 (检测 SD 卡 /sdcard/frames 目录) */
esp_err_t frame_player_init(void);

/** 释放帧播放器资源 */
void frame_player_deinit(void);

/** 开始播放指定状态的帧序列 */
esp_err_t frame_player_start(avatar_state_t state);

/** 停止播放 */
esp_err_t frame_player_stop(void);

/** 暂停/恢复 */
esp_err_t frame_player_pause(void);
esp_err_t frame_player_resume(void);

/** 设置状态 (等同于 start) */
esp_err_t frame_player_set_state(avatar_state_t state);

/** 查询状态 */
bool frame_player_is_playing(void);
bool frame_player_has_state(avatar_state_t state);
bool frame_player_is_sd_available(void);

/** 帧播放任务 (创建 FreeRTOS task, 每帧调 app_avatar_push_frame) */
void frame_player_task(void *pvParameter);

#endif /* FRAME_PLAYER_H */
