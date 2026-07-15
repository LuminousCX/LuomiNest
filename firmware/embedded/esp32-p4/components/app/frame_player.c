/**
 * LuomiNest P4 - SD 卡帧序列播放器
 * 从旧 esp32-p4/main/frame_player.c 移植, 适配新架构:
 *   - 帧输出走 app_avatar_push_frame() 而非旧回调
 *   - 用 cJSON 解析 manifest.json
 *   - SD 卡挂载由 bsp_sd 负责, 这里只读 /sdcard/frames/
 *
 * 设计选择 (KISS):
 *   - manifest.json 格式与旧工程完全兼容
 *   - 无 manifest 时自动扫描 /sdcard/frames/{state_name}/ 目录
 *   - 支持 JPEG 和 RAW (RGB565) 两种格式
 */

#include "frame_player.h"
#include "app_avatar.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "cJSON.h"
#include "esp_heap_caps.h"
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <dirent.h>

static const char *TAG = "frame_player";

static fp_context_t s_ctx = {0};
static SemaphoreHandle_t s_player_mux = NULL;
static volatile bool s_player_running = false;
static volatile avatar_state_t s_current_play_state = AVATAR_STATE_IDLE;
static volatile uint16_t s_current_frame_idx = 0;

static const char *state_dir_names[AVATAR_STATE_MAX] = {
    "idle", "happy", "sad", "angry", "surprised",
    "think", "neutral", "talk", "custom", "streaming"
};

static const char *fmt_exts[] = {
    [FP_FMT_AUTO] = "jpg",
    [FP_FMT_JPEG] = "jpg",
    [FP_FMT_RAW]  = "raw",
};

static bool _check_file_exists(const char *path)
{
    struct stat st;
    return (stat(path, &st) == 0);
}

static bool _check_dir_exists(const char *path)
{
    DIR *dir = opendir(path);
    if (dir) { closedir(dir); return true; }
    return false;
}

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wformat-truncation"

static int _count_frames_in_dir(const char *dir_path, fp_format_t fmt)
{
    const char *ext = fmt_exts[fmt];
    if (fmt == FP_FMT_AUTO) ext = "jpg";
    int count = 0;
    char filepath[FP_MAX_PATH];
    while (1) {
        snprintf(filepath, sizeof(filepath), "%s/%04u.%s", dir_path, (unsigned)(count + 1), ext);
        if (!_check_file_exists(filepath)) {
            if (fmt == FP_FMT_AUTO && count == 0) {
                snprintf(filepath, sizeof(filepath), "%s/%04u.raw", dir_path, (unsigned)(count + 1));
                if (_check_file_exists(filepath)) {
                    ext = "raw";
                    snprintf(filepath, sizeof(filepath), "%s/%04u.%s", dir_path, (unsigned)(count + 1), ext);
                    if (_check_file_exists(filepath)) { count++; continue; }
                }
            }
            break;
        }
        count++;
        if (count >= 9999) break;
    }
    return count;
}

static fp_format_t _detect_format_from_dir(const char *dir_path)
{
    char filepath[FP_MAX_PATH];
    snprintf(filepath, sizeof(filepath), "%s/0001.raw", dir_path);
    if (_check_file_exists(filepath)) return FP_FMT_RAW;
    snprintf(filepath, sizeof(filepath), "%s/0001.jpg", dir_path);
    if (_check_file_exists(filepath)) return FP_FMT_JPEG;
    return FP_FMT_AUTO;
}

static esp_err_t _auto_detect_sequences(void);

static esp_err_t _load_manifest(void)
{
    if (!_check_file_exists(FP_MANIFEST_FILE)) {
        ESP_LOGI(TAG, "No manifest.json found, auto-detecting frames...");
        return _auto_detect_sequences();
    }

    FILE *f = fopen(FP_MANIFEST_FILE, "r");
    if (!f) {
        ESP_LOGE(TAG, "Failed to open manifest.json");
        return ESP_FAIL;
    }

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fsize <= 0 || fsize > 65536) {
        fclose(f);
        return ESP_FAIL;
    }

    char *buf = heap_caps_malloc(fsize + 1, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!buf) { fclose(f); return ESP_ERR_NO_MEM; }

    fread(buf, 1, fsize, f);
    buf[fsize] = '\0';
    fclose(f);

    cJSON *root = cJSON_Parse(buf);
    free(buf);
    if (!root) return ESP_FAIL;

    cJSON *sequences = cJSON_GetObjectItem(root, "sequences");
    if (!sequences || !cJSON_IsArray(sequences)) {
        cJSON_Delete(root);
        return ESP_FAIL;
    }

    s_ctx.sequence_count = 0;
    int seq_count = cJSON_GetArraySize(sequences);
    for (int i = 0; i < seq_count && s_ctx.sequence_count < AVATAR_STATE_MAX; i++) {
        cJSON *seq = cJSON_GetArrayItem(sequences, i);
        cJSON *name_item = cJSON_GetObjectItem(seq, "name");
        cJSON *path_item = cJSON_GetObjectItem(seq, "path");
        cJSON *frame_count = cJSON_GetObjectItem(seq, "frame_count");
        cJSON *fps_item = cJSON_GetObjectItem(seq, "fps");
        cJSON *loop_item = cJSON_GetObjectItem(seq, "loop");
        cJSON *format_item = cJSON_GetObjectItem(seq, "format");

        if (!name_item || !cJSON_IsString(name_item)) continue;

        fp_sequence_t *s = &s_ctx.sequences[s_ctx.sequence_count];
        snprintf(s->name, sizeof(s->name), "%s", name_item->valuestring);

        if (path_item && cJSON_IsString(path_item))
            snprintf(s->path, sizeof(s->path), "%s", path_item->valuestring);
        else {
            char tmp[FP_MAX_STATE_NAME];
            snprintf(tmp, sizeof(tmp), "%s", s->name);
            snprintf(s->path, sizeof(s->path), "/sdcard/frames/%s", tmp);
        }

        s->frame_count = (frame_count && cJSON_IsNumber(frame_count)) ?
                          (uint16_t)frame_count->valueint : 0;
        s->fps = (fps_item && cJSON_IsNumber(fps_item)) ?
                  (uint16_t)fps_item->valueint : FP_DEFAULT_FPS;
        s->loop = (loop_item && cJSON_IsBool(loop_item)) ? cJSON_IsTrue(loop_item) : true;

        if (format_item && cJSON_IsString(format_item)) {
            if (strcmp(format_item->valuestring, "raw") == 0) s->format = FP_FMT_RAW;
            else s->format = FP_FMT_JPEG;
        } else {
            s->format = FP_FMT_AUTO;
        }

        if (s->format == FP_FMT_AUTO) s->format = _detect_format_from_dir(s->path);
        if (s->frame_count == 0) s->frame_count = _count_frames_in_dir(s->path, s->format);

        if (s->frame_count > 0) {
            ESP_LOGI(TAG, "Sequence[%d]: %s, %d frames @ %d fps, fmt=%s",
                     s_ctx.sequence_count, s->name, s->frame_count, s->fps,
                     s->format == FP_FMT_RAW ? "RAW" : "JPEG");
            s_ctx.sequence_count++;
        }
    }

    cJSON_Delete(root);
    ESP_LOGI(TAG, "Loaded %d sequences from manifest", s_ctx.sequence_count);
    return ESP_OK;
}

static esp_err_t _auto_detect_sequences(void)
{
    s_ctx.sequence_count = 0;
    for (int i = 0; i < AVATAR_STATE_MAX && s_ctx.sequence_count < AVATAR_STATE_MAX; i++) {
        char dir_path[FP_MAX_PATH];
        snprintf(dir_path, sizeof(dir_path), "/sdcard/frames/%s", state_dir_names[i]);
        if (!_check_dir_exists(dir_path)) continue;

        fp_format_t fmt = _detect_format_from_dir(dir_path);
        if (fmt == FP_FMT_AUTO) continue;

        int count = _count_frames_in_dir(dir_path, fmt);
        if (count <= 0) continue;

        fp_sequence_t *s = &s_ctx.sequences[s_ctx.sequence_count];
        snprintf(s->name, sizeof(s->name), "%s", state_dir_names[i]);
        snprintf(s->path, sizeof(s->path), "%s", dir_path);
        s->frame_count = count;
        s->fps = FP_DEFAULT_FPS;
        s->loop = true;
        s->format = fmt;

        ESP_LOGI(TAG, "Auto-detected: %s, %d frames, fmt=%s",
                 s->name, s->frame_count, s->format == FP_FMT_RAW ? "RAW" : "JPEG");
        s_ctx.sequence_count++;
    }
    ESP_LOGI(TAG, "Auto-detected %d sequences", s_ctx.sequence_count);
    return (s_ctx.sequence_count > 0) ? ESP_OK : ESP_ERR_NOT_FOUND;
}

#pragma GCC diagnostic pop

static fp_sequence_t *_find_sequence(avatar_state_t state)
{
    const char *name = state_dir_names[state];
    for (int i = 0; i < s_ctx.sequence_count; i++) {
        if (strcmp(s_ctx.sequences[i].name, name) == 0)
            return &s_ctx.sequences[i];
    }
    return NULL;
}

static esp_err_t _read_frame_file(const char *dir_path, uint16_t frame_idx,
                                   fp_format_t fmt, uint8_t **out_data, uint32_t *out_len)
{
    const char *ext = (fmt == FP_FMT_RAW) ? "raw" : "jpg";
    char filepath[FP_MAX_PATH];
    snprintf(filepath, sizeof(filepath), "%s/%04u.%s", dir_path, (unsigned)(frame_idx + 1), ext);

    FILE *f = fopen(filepath, "rb");
    if (!f) return ESP_ERR_NOT_FOUND;

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fsize <= 0 || fsize > 1024 * 1024) {
        fclose(f);
        return ESP_FAIL;
    }

    uint8_t *buf = heap_caps_malloc(fsize, MALLOC_CAP_SPIRAM);
    if (!buf) { fclose(f); return ESP_ERR_NO_MEM; }

    size_t read_len = fread(buf, 1, fsize, f);
    fclose(f);

    if (read_len != (size_t)fsize) {
        free(buf);
        return ESP_FAIL;
    }

    *out_data = buf;
    *out_len = (uint32_t)fsize;
    return ESP_OK;
}

esp_err_t frame_player_init(void)
{
    s_player_mux = xSemaphoreCreateMutex();
    if (!s_player_mux) return ESP_ERR_NO_MEM;

    memset(&s_ctx, 0, sizeof(s_ctx));

    if (!_check_dir_exists("/sdcard/frames")) {
        ESP_LOGI(TAG, "No /sdcard/frames directory, SD prerender not available");
        s_ctx.sd_available = false;
        return ESP_OK;
    }

    s_ctx.sd_available = true;
    esp_err_t ret = _load_manifest();
    if (ret != ESP_OK) {
        s_ctx.sd_available = (s_ctx.sequence_count > 0);
    }

    ESP_LOGI(TAG, "Frame player initialized: %d sequences, SD=%s",
             s_ctx.sequence_count, s_ctx.sd_available ? "yes" : "no");
    return ESP_OK;
}

void frame_player_deinit(void)
{
    s_player_running = false;
    vTaskDelay(pdMS_TO_TICKS(100));  /* 等待 task 自行退出 */
    if (s_player_mux) {
        vSemaphoreDelete(s_player_mux);
        s_player_mux = NULL;
    }
    memset(&s_ctx, 0, sizeof(s_ctx));
}

esp_err_t frame_player_start(avatar_state_t state)
{
    if (!s_ctx.sd_available) return ESP_ERR_INVALID_STATE;

    fp_sequence_t *seq = _find_sequence(state);
    if (!seq) return ESP_ERR_NOT_FOUND;

    xSemaphoreTake(s_player_mux, portMAX_DELAY);
    s_current_play_state = state;
    s_current_frame_idx = 0;
    s_ctx.mode = FP_MODE_PLAYING;
    xSemaphoreGive(s_player_mux);

    ESP_LOGI(TAG, "Playing: %s (%d frames @ %d fps)",
             seq->name, seq->frame_count, seq->fps);
    return ESP_OK;
}

esp_err_t frame_player_stop(void)
{
    xSemaphoreTake(s_player_mux, portMAX_DELAY);
    s_ctx.mode = FP_MODE_IDLE;
    s_current_frame_idx = 0;
    xSemaphoreGive(s_player_mux);
    return ESP_OK;
}

esp_err_t frame_player_pause(void)
{
    xSemaphoreTake(s_player_mux, portMAX_DELAY);
    if (s_ctx.mode == FP_MODE_PLAYING) s_ctx.mode = FP_MODE_PAUSED;
    xSemaphoreGive(s_player_mux);
    return ESP_OK;
}

esp_err_t frame_player_resume(void)
{
    xSemaphoreTake(s_player_mux, portMAX_DELAY);
    if (s_ctx.mode == FP_MODE_PAUSED) s_ctx.mode = FP_MODE_PLAYING;
    xSemaphoreGive(s_player_mux);
    return ESP_OK;
}

esp_err_t frame_player_set_state(avatar_state_t state) { return frame_player_start(state); }
bool frame_player_is_playing(void) { return s_ctx.mode == FP_MODE_PLAYING; }
bool frame_player_has_state(avatar_state_t state) { return _find_sequence(state) != NULL; }
bool frame_player_is_sd_available(void) { return s_ctx.sd_available; }

void frame_player_task(void *pvParameter)
{
    (void)pvParameter;
    ESP_LOGI(TAG, "Frame player task started");
    s_player_running = true;

    while (s_player_running) {
        xSemaphoreTake(s_player_mux, portMAX_DELAY);
        fp_playback_mode_t mode = s_ctx.mode;
        avatar_state_t play_state = s_current_play_state;
        uint16_t frame_idx = s_current_frame_idx;
        xSemaphoreGive(s_player_mux);

        if (mode != FP_MODE_PLAYING) {
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }

        fp_sequence_t *seq = _find_sequence(play_state);
        if (!seq) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        /* 队列满时等待解码完成 */
        while (!app_avatar_queue_has_space()) {
            vTaskDelay(pdMS_TO_TICKS(10));
        }

        uint8_t *frame_data = NULL;
        uint32_t frame_len = 0;
        esp_err_t ret = _read_frame_file(seq->path, frame_idx, seq->format,
                                          &frame_data, &frame_len);
        if (ret == ESP_OK && frame_data) {
            /* 零拷贝: 直接把 SD 卡读出的 buffer 传给 avatar, 不走 push_frame 的二次拷贝 */
            jpg_entry_t entry = { .data = frame_data, .len = frame_len };
            if (xQueueSend(app_avatar_get_queue(), &entry, 0) != pdTRUE) {
                free(frame_data);  /* 队列满才释放 */
            }
        }

        xSemaphoreTake(s_player_mux, portMAX_DELAY);
        s_current_frame_idx++;
        if (s_current_frame_idx >= seq->frame_count) {
            if (seq->loop)
                s_current_frame_idx = 0;
            else
                s_ctx.mode = FP_MODE_IDLE;
        }
        xSemaphoreGive(s_player_mux);

        uint32_t frame_delay_ms = 1000 / seq->fps;
        if (frame_delay_ms < 8) frame_delay_ms = 8;
        vTaskDelay(pdMS_TO_TICKS(frame_delay_ms));
    }

    ESP_LOGI(TAG, "Frame player task stopped");
    vTaskDelete(NULL);
}
