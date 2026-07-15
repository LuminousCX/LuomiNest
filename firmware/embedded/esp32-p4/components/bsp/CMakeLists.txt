idf_component_register(
    SRCS "bsp_lcd.c" "bsp_touch.c" "bsp_spi_p4.c" "bsp_sd.c" "bsp_eth.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_lcd esp_driver_spi sdmmc vfs fatfs esp_eth esp_netif esp_lcd_touch
    PRIV_REQUIRES esp_lcd_jd9165 esp_lcd_touch_gt911
)
