#include "frame_player.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "cJSON.h"
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
static fp_frame_ready_cb_t s_frame_cb = NULL;

static const char *state_dir_names[AVATAR_STATE_MAX] = {
    "idle", "happy", "sad", "angry", "surprised",
    "think", "neutral", "talk", "custom", "streaming"
};

static bool _check_file_exists(const char *path)
{
    struct stat st;
    return (stat(path, &st) == 0);
}

static bool _check_dir_exists(const char *path)
{
    DIR *dir = opendir(path);
    if (dir) {
        closedir(dir);
        return true;
    }
    return false;
}

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wformat-truncation"

static int _count_frames_in_dir(const char *dir_path)
{
    int count = 0;
    char filepath[FP_MAX_PATH];
    while (1) {
        snprintf(filepath, sizeof(filepath), "%s/%04u.jpg", dir_path, (unsigned)(count + 1));
        if (!_check_file_exists(filepath)) break;
        count++;
        if (count >= 9999) break;
    }
    return count;
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
        ESP_LOGE(TAG, "Manifest too large or empty (%ld bytes)", fsize);
        return ESP_FAIL;
    }

    char *buf = malloc(fsize + 1);
    if (!buf) {
        fclose(f);
        return ESP_ERR_NO_MEM;
    }

    fread(buf, 1, fsize, f);
    buf[fsize] = '\0';
    fclose(f);

    cJSON *root = cJSON_Parse(buf);
    free(buf);
    if (!root) {
        ESP_LOGE(TAG, "Failed to parse manifest.json");
        return ESP_FAIL;
    }

    cJSON *sequences = cJSON_GetObjectItem(root, "sequences");
    if (!sequences || !cJSON_IsArray(sequences)) {
        cJSON_Delete(root);
        ESP_LOGE(TAG, "No 'sequences' array in manifest");
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

        if (!name_item || !cJSON_IsString(name_item)) continue;

        fp_sequence_t *s = &s_ctx.sequences[s_ctx.sequence_count];
        char tmp_name[FP_MAX_STATE_NAME];
        snprintf(tmp_name, sizeof(tmp_name), "%s", name_item->valuestring);
        snprintf(s->name, sizeof(s->name), "%s", tmp_name);

        if (path_item && cJSON_IsString(path_item)) {
            snprintf(s->path, sizeof(s->path), "%s", path_item->valuestring);
        } else {
            snprintf(s->path, sizeof(s->path), "/sdcard/frames/%s", tmp_name);
        }

        s->frame_count = (frame_count && cJSON_IsNumber(frame_count)) ?
                          (uint16_t)frame_count->valueint : 0;
        s->fps = (fps_item && cJSON_IsNumber(fps_item)) ?
                  (uint16_t)fps_item->valueint : FP_DEFAULT_FPS;
        s->loop = (loop_item && cJSON_IsBool(loop_item)) ? cJSON_IsTrue(loop_item) : true;

        if (s->frame_count == 0) {
            s->frame_count = _count_frames_in_dir(s->path);
        }

        if (s->frame_count > 0) {
            ESP_LOGI(TAG, "Sequence[%d]: %s, %d frames @ %d fps, loop=%d, path=%s",
                     s_ctx.sequence_count, s->name, s->frame_count, s->fps, s->loop, s->path);
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
        const char *dir_name = state_dir_names[i];
        char dir_path[FP_MAX_PATH];
        snprintf(dir_path, sizeof(dir_path), "/sdcard/frames/%s", dir_name);

        if (!_check_dir_exists(dir_path)) continue;

        int count = _count_frames_in_dir(dir_path);
        if (count <= 0) continue;

        fp_sequence_t *s = &s_ctx.sequences[s_ctx.sequence_count];
        snprintf(s->name, sizeof(s->name), "%s", dir_name);
        snprintf(s->path, sizeof(s->path), "%s", dir_path);
        s->frame_count = count;
        s->fps = FP_DEFAULT_FPS;
        s->loop = true;

        ESP_LOGI(TAG, "Auto-detected: %s, %d frames, path=%s",
                 s->name, s->frame_count, s->path);
        s_ctx.sequence_count++;
    }

    ESP_LOGI(TAG, "Auto-detected %d sequences", s_ctx.sequence_count);
    return (s_ctx.sequence_count > 0) ? ESP_OK : ESP_ERR_NOT_FOUND;
}

static fp_sequence_t *_find_sequence(avatar_state_t state)
{
    const char *name = state_dir_names[state];
    for (int i = 0; i < s_ctx.sequence_count; i++) {
        if (strcmp(s_ctx.sequences[i].name, name) == 0) {
            return &s_ctx.sequences[i];
        }
    }
    return NULL;
}

static esp_err_t _read_frame_file(const char *dir_path, uint16_t frame_idx,
                                   uint8_t **out_data, uint32_t *out_len)
{
    char filepath[FP_MAX_PATH];
    snprintf(filepath, sizeof(filepath), "%s/%04u.jpg", dir_path, (unsigned)(frame_idx + 1));

    FILE *f = fopen(filepath, "rb");
    if (!f) {
        ESP_LOGD(TAG, "Cannot open %s", filepath);
        return ESP_ERR_NOT_FOUND;
    }

    fseek(f, 0, SEEK_END);
    long fsize = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (fsize <= 0 || fsize > 512 * 1024) {
        fclose(f);
        ESP_LOGW(TAG, "Frame file invalid size: %ld", fsize);
        return ESP_FAIL;
    }

    uint8_t *buf = heap_caps_malloc(fsize, MALLOC_CAP_SPIRAM);
    if (!buf) {
        fclose(f);
        return ESP_ERR_NO_MEM;
    }

    size_t read_len = fread(buf, 1, fsize, f);
    fclose(f);

    if (read_len != (size_t)fsize) {
        free(buf);
        ESP_LOGW(TAG, "Short read: %d/%ld", (int)read_len, fsize);
        return ESP_FAIL;
    }

    *out_data = buf;
    *out_len = (uint32_t)fsize;
    return ESP_OK;
}

#pragma GCC diagnostic pop

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
        ESP_LOGW(TAG, "No prerendered frames found on SD card");
        s_ctx.sd_available = (s_ctx.sequence_count > 0);
    }

    ESP_LOGI(TAG, "Frame player initialized: %d sequences, SD=%s",
             s_ctx.sequence_count, s_ctx.sd_available ? "yes" : "no");
    return ESP_OK;
}

esp_err_t frame_player_start(avatar_state_t state)
{
    if (!s_ctx.sd_available) return ESP_ERR_INVALID_STATE;

    fp_sequence_t *seq = _find_sequence(state);
    if (!seq) {
        ESP_LOGD(TAG, "No sequence for state %d (%s)", state, state_dir_names[state]);
        return ESP_ERR_NOT_FOUND;
    }

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
    if (s_ctx.mode == FP_MODE_PLAYING) {
        s_ctx.mode = FP_MODE_PAUSED;
    }
    xSemaphoreGive(s_player_mux);
    return ESP_OK;
}

esp_err_t frame_player_resume(void)
{
    xSemaphoreTake(s_player_mux, portMAX_DELAY);
    if (s_ctx.mode == FP_MODE_PAUSED) {
        s_ctx.mode = FP_MODE_PLAYING;
    }
    xSemaphoreGive(s_player_mux);
    return ESP_OK;
}

esp_err_t frame_player_set_state(avatar_state_t state)
{
    return frame_player_start(state);
}

bool frame_player_is_playing(void)
{
    return s_ctx.mode == FP_MODE_PLAYING;
}

bool frame_player_has_state(avatar_state_t state)
{
    return _find_sequence(state) != NULL;
}

bool frame_player_is_sd_available(void)
{
    return s_ctx.sd_available;
}

void frame_player_register_frame_cb(fp_frame_ready_cb_t cb)
{
    s_frame_cb = cb;
}

void frame_player_task(void *pvParameter)
{
    ESP_LOGI(TAG, "Frame player task started on core %d", xPortGetCoreID());

    s_player_running = true;
    uint8_t *frame_data = NULL;
    uint32_t frame_len = 0;

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

        esp_err_t ret = _read_frame_file(seq->path, frame_idx, &frame_data, &frame_len);
        if (ret == ESP_OK && frame_data && s_frame_cb) {
            s_frame_cb(frame_data, frame_len);
            free(frame_data);
            frame_data = NULL;
        } else {
            if (frame_data) {
                free(frame_data);
                frame_data = NULL;
            }
        }

        xSemaphoreTake(s_player_mux, portMAX_DELAY);
        s_current_frame_idx++;
        if (s_current_frame_idx >= seq->frame_count) {
            if (seq->loop) {
                s_current_frame_idx = 0;
            } else {
                s_ctx.mode = FP_MODE_IDLE;
            }
        }
        xSemaphoreGive(s_player_mux);

        uint32_t frame_delay_ms = 1000 / seq->fps;
        if (frame_delay_ms < 16) frame_delay_ms = 16;
        vTaskDelay(pdMS_TO_TICKS(frame_delay_ms));
    }

    ESP_LOGI(TAG, "Frame player task stopped");
    vTaskDelete(NULL);
}
