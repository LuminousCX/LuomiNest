#ifndef SPI_FRAME_RX_H
#define SPI_FRAME_RX_H

#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>

typedef void (*spi_frame_cb_t)(const uint8_t *data, uint32_t len);

esp_err_t spi_frame_rx_init(void);
esp_err_t spi_frame_rx_register_cb(spi_frame_cb_t cb);
esp_err_t spi_frame_rx_start(void);
esp_err_t spi_frame_rx_stop(void);
bool spi_frame_rx_is_running(void);

#endif
