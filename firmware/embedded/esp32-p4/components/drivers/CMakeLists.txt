idf_component_register(
    SRCS "drv_jpeg.c" "drv_spi_master.c"
    INCLUDE_DIRS "."
    REQUIRES bsp driver esp_lcd esp_timer
    PRIV_REQUIRES esp_jpeg
)
