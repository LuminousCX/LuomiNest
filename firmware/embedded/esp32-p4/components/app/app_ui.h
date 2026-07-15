/**
 * LuomiNest P4 - APP UI 全屏布局管理
 * 从旧 esp32-p4/main/main.c create_ui() 移植, 适配新分层架构:
 *   - 状态栏 (24px): 标题 + 连接状态 + 网络 + 时间 + 设置按钮
 *   - 水平滑动页面: Page 0 (chat 左 + avatar 右) / Page 1 (设置)
 *   - 底部页码指示器 (2 dots)
 */

#ifndef APP_UI_H
#define APP_UI_H

#include "lvgl.h"
#include "esp_err.h"

/** 初始化全屏 LVGL 布局, 内部调 app_chat_init + app_avatar_init + settings_ui_init. */
esp_err_t app_ui_init(void);

/** 更新状态栏标签 (app_status / app_mqtt 回调调). */
void app_ui_set_status(const char *text, lv_color_t color);
void app_ui_set_net_info(const char *text);
void app_ui_set_time(const char *text);

/** 获取右侧 avatar 面板 (供 deferred_init_task 调 app_avatar_init). */
lv_obj_t *app_ui_get_right_panel(void);

#endif /* APP_UI_H */
