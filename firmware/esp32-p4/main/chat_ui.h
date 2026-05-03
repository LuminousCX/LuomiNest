#ifndef CHAT_UI_H
#define CHAT_UI_H

#include "lvgl.h"
#include "esp_err.h"

#define CHAT_MSG_MAX_LEN  512
#define CHAT_MAX_MESSAGES 64

typedef enum {
    CHAT_MSG_USER = 0,
    CHAT_MSG_ASSISTANT,
} chat_msg_role_t;

typedef struct {
    chat_msg_role_t role;
    char text[CHAT_MSG_MAX_LEN];
} chat_msg_t;

typedef struct {
    lv_obj_t *panel;
    lv_obj_t *cont;
    lv_obj_t *msg_list;
    chat_msg_t messages[CHAT_MAX_MESSAGES];
    uint16_t count;
} chat_ui_t;

esp_err_t chat_ui_init(chat_ui_t *chat, lv_obj_t *parent, int32_t width, int32_t height);
esp_err_t chat_ui_add_message(chat_ui_t *chat, chat_msg_role_t role, const char *text);
void chat_ui_scroll_to_bottom(chat_ui_t *chat);
void chat_ui_clear(chat_ui_t *chat);
void chat_ui_add_demo_messages(chat_ui_t *chat);

#endif
