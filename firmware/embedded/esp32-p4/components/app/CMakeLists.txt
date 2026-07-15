idf_component_register(
    SRCS "app_ui.c" "app_avatar.c" "app_chat.c" "app_spi_recv.c" "app_status.c"
         "web_config.c" "time_mgr.c" "app_mqtt.c" "frame_player.c" "settings_ui.c"
    INCLUDE_DIRS "."
    REQUIRES bsp drivers freertos nvs_flash
    PRIV_REQUIRES lvgl esp_lvgl_port mqtt json
)
